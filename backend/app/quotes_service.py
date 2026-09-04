"""
Glue between the shared cache (market_data_cache.py, filled by the
background poller) and a request that needs quotes right now — e.g. a
symbol was just added to a watchlist and hasn't been through a poll cycle
yet. Routes should call get_current_quotes() rather than touching the
cache or AlpacaClient directly.
"""
from __future__ import annotations

from app.config import settings
from app.market_data import AlpacaClient, AssetClass, MarketDataUnavailable, Quote
from app.market_data_cache import quote_cache


def get_current_quotes(
    symbols_by_class: dict[AssetClass, list[str]], client: AlpacaClient | None = None
) -> dict[str, Quote]:
    """Cache-first lookup; any symbol missing from the cache (e.g. just
    added, poller hasn't run yet) is fetched synchronously so the user
    isn't staring at an empty row on first add. A failure here is caught
    and simply leaves that symbol absent from the result — callers already
    treat a missing symbol as "no data," not an error (see §8)."""
    client = client or AlpacaClient()
    result: dict[str, Quote] = {}

    for asset_class, symbols in symbols_by_class.items():
        if not symbols:
            continue
        cached = quote_cache.get_many(symbols, asset_class)
        for symbol, cached_quote in cached.items():
            result[symbol] = cached_quote.quote

        missing = [s for s in symbols if s not in cached]
        if not missing:
            continue
        try:
            fresh = client.get_snapshots(missing, asset_class)
            for symbol, quote in fresh.items():
                quote_cache.set(symbol, quote)
                result[symbol] = quote
        except MarketDataUnavailable:
            pass  # missing symbols just stay missing this request — no crash

    return result


def get_index_quote(client: AlpacaClient | None = None) -> Quote | None:
    quotes = get_current_quotes({AssetClass.STOCK: [settings.INDEX_BASELINE_SYMBOL]}, client)
    return quotes.get(settings.INDEX_BASELINE_SYMBOL)


def is_stale(symbol: str, asset_class: AssetClass) -> bool:
    cached = quote_cache.get(symbol, asset_class)
    return bool(cached and cached.stale)
