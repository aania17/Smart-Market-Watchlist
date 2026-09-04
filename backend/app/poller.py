"""
Background poller — refreshes app.market_data_cache.quote_cache on an
interval, for the deduplicated union of every symbol currently in any
user's watchlist. This is the piece that answers "how does it scale":
one poll cycle serves every user, regardless of how many are watching the
same symbol.

Started from main.py's startup event; runs for the lifetime of the process.
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.market_data import AlpacaClient, AssetClass, MarketDataUnavailable
from app.market_data_cache import quote_cache
from app.models import WatchlistItem

logger = logging.getLogger(__name__)


def get_watched_symbols(db: Session) -> dict[AssetClass, list[str]]:
    """The deduplicated union of every symbol any user is watching,
    grouped by asset class (stocks and crypto hit different Alpaca
    endpoints — see market_data.py)."""
    rows = db.execute(select(WatchlistItem.symbol, WatchlistItem.asset_class).distinct()).all()
    by_class: dict[AssetClass, set[str]] = {AssetClass.STOCK: set(), AssetClass.CRYPTO: set()}
    for symbol, asset_class in rows:
        by_class[AssetClass(asset_class)].add(symbol)
    return {k: sorted(v) for k, v in by_class.items()}


def poll_once(db: Session, client: AlpacaClient | None = None) -> None:
    """One poll cycle: fetch current snapshots for every watched symbol
    and update the shared cache. On upstream failure, mark already-cached
    symbols stale rather than clearing them — §8's "serve last-known-good"
    rule."""
    client = client or AlpacaClient()
    watched = get_watched_symbols(db)

    for asset_class, symbols in watched.items():
        if not symbols:
            continue
        try:
            quotes = client.get_snapshots(symbols, asset_class)
            for symbol, quote in quotes.items():
                quote_cache.set(symbol, quote)
            missing = set(symbols) - set(quotes.keys())
            for symbol in missing:
                quote_cache.mark_stale(symbol, asset_class)
        except MarketDataUnavailable as exc:
            logger.warning("Poll failed for %s symbols (%s): %s", asset_class.value, len(symbols), exc)
            for symbol in symbols:
                quote_cache.mark_stale(symbol, asset_class)


async def run_poller(session_factory) -> None:
    """Long-running loop — call once from a startup event with
    `asyncio.create_task(run_poller(SessionLocal))`."""
    while True:
        await asyncio.to_thread(_run_poll_cycle, session_factory)
        await asyncio.sleep(settings.QUOTE_POLL_INTERVAL_SECONDS)


def _run_poll_cycle(session_factory) -> None:
    """Run blocking provider and database work away from the event loop."""
    db = session_factory()
    try:
        poll_once(db)
    except Exception:  # noqa: BLE001 — never let the poller die silently
        logger.exception("Unexpected error in poll cycle")
    finally:
        db.close()
