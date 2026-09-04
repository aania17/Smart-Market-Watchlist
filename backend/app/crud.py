from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app import models, schemas


def get_user_by_email(db: Session, email: str) -> models.User | None:
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, user_in: schemas.UserCreate) -> models.User:
    from app.auth import hash_password  # local import avoids a circular import with auth.py

    user = models.User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ---------------- Watchlists ----------------
def create_watchlist(db: Session, owner_id: int, name: str) -> models.Watchlist:
    watchlist = models.Watchlist(owner_id=owner_id, name=name)
    db.add(watchlist)
    db.commit()
    db.refresh(watchlist)
    return watchlist


def list_watchlists_for_user(db: Session, owner_id: int) -> list[models.Watchlist]:
    return db.query(models.Watchlist).filter(models.Watchlist.owner_id == owner_id).all()


def get_watchlist(db: Session, watchlist_id: int, owner_id: int) -> models.Watchlist | None:
    return (
        db.query(models.Watchlist)
        .filter(models.Watchlist.id == watchlist_id, models.Watchlist.owner_id == owner_id)
        .first()
    )


def delete_watchlist(db: Session, watchlist: models.Watchlist) -> None:
    db.delete(watchlist)
    db.commit()


def update_watchlist_threshold(db: Session, watchlist: models.Watchlist, threshold_pct: float) -> models.Watchlist:
    watchlist.meaningful_threshold_pct = threshold_pct
    db.commit()
    db.refresh(watchlist)
    return watchlist


# ---------------- Watchlist items ----------------
def add_watchlist_item(
    db: Session, watchlist_id: int, symbol: str, asset_class: str, quantity: float | None = None
) -> models.WatchlistItem:
    existing = (
        db.query(models.WatchlistItem)
        .filter(models.WatchlistItem.watchlist_id == watchlist_id, models.WatchlistItem.symbol == symbol)
        .first()
    )
    if existing:
        return existing  # idempotent add — avoids a duplicate-key race on double-click/retry
    item = models.WatchlistItem(watchlist_id=watchlist_id, symbol=symbol, asset_class=asset_class, quantity=quantity)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_item_quantity(
    db: Session, watchlist_id: int, symbol: str, quantity: float | None
) -> models.WatchlistItem | None:
    item = (
        db.query(models.WatchlistItem)
        .filter(models.WatchlistItem.watchlist_id == watchlist_id, models.WatchlistItem.symbol == symbol)
        .first()
    )
    if item is None:
        return None
    item.quantity = quantity
    db.commit()
    db.refresh(item)
    return item


def remove_watchlist_item(db: Session, watchlist_id: int, symbol: str) -> None:
    db.query(models.WatchlistItem).filter(
        models.WatchlistItem.watchlist_id == watchlist_id, models.WatchlistItem.symbol == symbol
    ).delete()
    db.commit()


def list_watchlist_items(db: Session, watchlist_id: int) -> list[models.WatchlistItem]:
    return db.query(models.WatchlistItem).filter(models.WatchlistItem.watchlist_id == watchlist_id).all()


# ---------------- Price snapshots (§5 state persistence) ----------------
def get_snapshot_map(db: Session, watchlist_id: int) -> dict[str, models.PriceSnapshot]:
    rows = db.query(models.PriceSnapshot).filter(models.PriceSnapshot.watchlist_id == watchlist_id).all()
    return {row.symbol: row for row in rows}


def upsert_snapshots(db: Session, watchlist_id: int, prices: dict[str, float], captured_at: datetime) -> None:
    """Overwrite the "last visit" price for each symbol. Called once per
    watchlist view, AFTER the change signals for this view have already
    been computed against the OLD snapshot — see the route in main.py for
    why ordering here matters (§5's diff-then-update flow)."""
    existing = get_snapshot_map(db, watchlist_id)
    for symbol, price in prices.items():
        if symbol in existing:
            existing[symbol].price = price
            existing[symbol].captured_at = captured_at
        else:
            db.add(
                models.PriceSnapshot(
                    watchlist_id=watchlist_id, symbol=symbol, price=price, captured_at=captured_at
                )
            )
    db.commit()


def update_last_viewed(db: Session, watchlist: models.Watchlist, when: datetime | None = None) -> None:
    watchlist.last_viewed_at = when or datetime.now(timezone.utc)
    db.commit()
