import asyncio
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.auth import create_access_token, get_current_user, verify_password
from app.change_detection import build_change_signal
from app.briefing import build_briefing, build_move_groups
from app.config import settings
from app.database import Base, SessionLocal, engine, ensure_schema_compatibility, get_db
from app.market_data import AlpacaClient, AssetClass, MarketDataUnavailable
from app.poller import run_poller
from app.quotes_service import get_current_quotes, get_index_quote, is_stale

# Creates tables on startup if they don't exist yet — convenient for a fresh
# Supabase project. Use Alembic for production schema changes after seeding.
Base.metadata.create_all(bind=engine)
ensure_schema_compatibility()

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def start_background_poller():
    # Fire-and-forget background task — see app/poller.py. If ALPACA keys
    # aren't set yet (e.g. first local run before .env is filled in), the
    # poller will just log failures each cycle rather than crashing the app.
    asyncio.create_task(run_poller(SessionLocal))


@app.get("/health")
def health():
    """Hit this from the frontend on load to confirm the API is reachable."""
    return {"status": "ok"}


# ---------------- Auth ----------------
@app.post("/auth/signup", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def signup(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    if crud.get_user_by_email(db, user_in.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db, user_in)


@app.post("/auth/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # OAuth2PasswordRequestForm sends "username" — we treat it as email
    user = crud.get_user_by_email(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    token = create_access_token({"sub": str(user.id)})
    return schemas.Token(access_token=token)


@app.get("/auth/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user


# ---------------- Watchlists ----------------
@app.post("/watchlists", response_model=schemas.WatchlistOut, status_code=status.HTTP_201_CREATED)
def create_watchlist(
    watchlist_in: schemas.WatchlistCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.create_watchlist(db, owner_id=current_user.id, name=watchlist_in.name)


@app.get("/watchlists", response_model=list[schemas.WatchlistOut])
def list_watchlists(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.list_watchlists_for_user(db, owner_id=current_user.id)


def _get_owned_watchlist(db: Session, watchlist_id: int, current_user: models.User) -> models.Watchlist:
    watchlist = crud.get_watchlist(db, watchlist_id, owner_id=current_user.id)
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return watchlist


@app.delete("/watchlists/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist(
    watchlist_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    watchlist = _get_owned_watchlist(db, watchlist_id, current_user)
    crud.delete_watchlist(db, watchlist)


# ---------------- Watchlist items ----------------
@app.post(
    "/watchlists/{watchlist_id}/items",
    response_model=schemas.WatchlistItemOut,
    status_code=status.HTTP_201_CREATED,
)
def add_item(
    watchlist_id: int,
    item_in: schemas.WatchlistItemCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _get_owned_watchlist(db, watchlist_id, current_user)
    symbol = item_in.symbol.strip().upper() if item_in.asset_class == AssetClass.STOCK.value else item_in.symbol.strip()
    return crud.add_watchlist_item(
        db, watchlist_id, symbol=symbol, asset_class=item_in.asset_class, quantity=item_in.quantity
    )


@app.patch("/watchlists/{watchlist_id}/sensitivity", response_model=schemas.WatchlistOut)
def update_sensitivity(
    watchlist_id: int,
    update: schemas.SensitivityUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    watchlist = _get_owned_watchlist(db, watchlist_id, current_user)
    return crud.update_watchlist_threshold(db, watchlist, update.meaningful_threshold_pct)


@app.patch("/watchlists/{watchlist_id}/items/quantity", response_model=schemas.WatchlistItemOut)
def update_quantity(
    watchlist_id: int,
    symbol: str,
    update: schemas.QuantityUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _get_owned_watchlist(db, watchlist_id, current_user)
    item = crud.update_item_quantity(db, watchlist_id, symbol, update.quantity)
    if item is None:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    return item


@app.delete("/watchlists/{watchlist_id}/items", status_code=status.HTTP_204_NO_CONTENT)
def remove_item(
    watchlist_id: int,
    symbol: str,  # query param, e.g. /items?symbol=BTC/USD — a path param would break on the slash
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _get_owned_watchlist(db, watchlist_id, current_user)
    crud.remove_watchlist_item(db, watchlist_id, symbol=symbol)


# ---------------- The core endpoint: view + diff ----------------
@app.get("/watchlists/{watchlist_id}/view", response_model=schemas.WatchlistViewOut)
def view_watchlist(
    watchlist_id: int,
    update_baseline: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Implements §4 and §5 of the requirements doc in one flow:
    1. Read the OLD snapshot + OLD last_viewed_at (the "last time you looked").
    2. Fetch current prices (cache-first, see quotes_service.py).
    3. Compute change signals by diffing current vs. old — this must happen
       BEFORE step 4 overwrites the snapshot, or there'd be nothing left to
       diff against.
     4. Only overwrite the snapshot + last_viewed_at when the user explicitly
         acknowledges the changes with update_baseline=true.
    """
    watchlist = _get_owned_watchlist(db, watchlist_id, current_user)
    items = crud.list_watchlist_items(db, watchlist_id)

    old_snapshots = crud.get_snapshot_map(db, watchlist_id)  # step 1
    old_last_viewed_at = watchlist.last_viewed_at

    symbols_by_class: dict[AssetClass, list[str]] = {AssetClass.STOCK: [], AssetClass.CRYPTO: []}
    for item in items:
        symbols_by_class[AssetClass(item.asset_class)].append(item.symbol)

    current_quotes = get_current_quotes(symbols_by_class)  # step 2
    index_quote = get_index_quote() if symbols_by_class[AssetClass.STOCK] else None

    signals = []
    fresh_prices: dict[str, float] = {}
    for item in items:
        quote = current_quotes.get(item.symbol)
        if quote is None:
            continue  # no data available for this symbol right now — omit rather than fabricate
        old_snapshot = old_snapshots.get(item.symbol)
        signal = build_change_signal(  # step 3
            quote=quote,
            last_visit_price=old_snapshot.price if old_snapshot else None,
            last_visit_at=old_last_viewed_at,
            index_quote=index_quote,
            is_stale=is_stale(item.symbol, AssetClass(item.asset_class)),
            quantity=item.quantity,
        )
        signals.append(signal)
        fresh_prices[item.symbol] = quote.price

    threshold_pct = watchlist.meaningful_threshold_pct or 2.0
    briefing = build_briefing(signals, old_last_viewed_at, threshold_pct)
    move_groups = build_move_groups(signals, threshold_pct)
    if update_baseline:
        now = datetime.now(timezone.utc)
        crud.upsert_snapshots(db, watchlist_id, fresh_prices, captured_at=now)  # step 4
        crud.update_last_viewed(db, watchlist, when=now)

    # Surface the most meaningful changes first — this is the whole point.
    signals.sort(key=lambda s: (not s.is_meaningful(threshold_pct), -(abs(s.change_since_last_visit_pct or 0))))

    return schemas.WatchlistViewOut(
        watchlist=schemas.WatchlistOut.model_validate(watchlist),
        items=[schemas.WatchlistItemOut.model_validate(item) for item in items],
        signals=[schemas.ChangeSignalOut(**s.__dict__, is_meaningful=s.is_meaningful(threshold_pct)) for s in signals],
        briefing=briefing,
        move_groups=[schemas.MoveGroupOut(**group.__dict__) for group in move_groups],
    )


@app.get("/watchlists/{watchlist_id}/hourly", response_model=list[schemas.HourlySeriesOut])
def hourly_watchlist(
    watchlist_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return hourly closes from the beginning of the current UTC day."""
    watchlist = _get_owned_watchlist(db, watchlist_id, current_user)
    items = crud.list_watchlist_items(db, watchlist.id)
    symbols_by_class: dict[AssetClass, list[str]] = {AssetClass.STOCK: [], AssetClass.CRYPTO: []}
    for item in items:
        symbols_by_class[AssetClass(item.asset_class)].append(item.symbol)

    client = AlpacaClient()
    end = datetime.now(timezone.utc)
    start = end.replace(hour=0, minute=0, second=0, microsecond=0)
    series: list[schemas.HourlySeriesOut] = []
    for asset_class, symbols in symbols_by_class.items():
        if not symbols:
            continue
        try:
            bars_by_symbol = client.get_hourly_bars(symbols, asset_class, start, end)
        except MarketDataUnavailable:
            bars_by_symbol = {}
        for symbol in symbols:
            bars = bars_by_symbol.get(symbol, [])
            points = [schemas.HourlyPointOut(timestamp=bar.timestamp, price=float(bar.close)) for bar in bars]
            first = points[0].price if points else None
            last = points[-1].price if points else None
            change_pct = round((last - first) / first * 100, 4) if first else None
            series.append(
                schemas.HourlySeriesOut(
                    symbol=symbol,
                    asset_class=asset_class.value,
                    points=points,
                    change_pct=change_pct,
                )
            )
    return series
