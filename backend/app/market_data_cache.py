"""
Shared, in-process cache for current quotes.

This is what makes the §7 scaling argument real: every user's watchlist
read hits this cache, never Alpaca directly. A single background poller
(see poller.py) is the only thing that talks to the network for live
prices — so 50 users watching AAPL costs one upstream call per poll
interval, not 50.

Deliberately a plain dict, not Redis: for a single-process hackathon
deployment this is simpler and has zero extra infra to deploy or debug
under time pressure. If this needed to run multi-process, swapping this
module's internals for Redis wouldn't change any caller — that's the
scaling story to state in the README, not necessarily to build.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.market_data import AssetClass, Quote


@dataclass
class CachedQuote:
    quote: Quote
    fetched_at: datetime
    stale: bool = False  # True if this is a last-known-good value being
    # served after an upstream failure — see §8 "stale data" handling


class QuoteCache:
    def __init__(self):
        self._store: dict[tuple[AssetClass, str], CachedQuote] = {}

    def get(self, symbol: str, asset_class: AssetClass) -> CachedQuote | None:
        return self._store.get((asset_class, symbol))

    def get_many(self, symbols: list[str], asset_class: AssetClass) -> dict[str, CachedQuote]:
        return {s: self._store[(asset_class, s)] for s in symbols if (asset_class, s) in self._store}

    def set(self, symbol: str, quote: Quote):
        self._store[(quote.asset_class, symbol)] = CachedQuote(
            quote=quote, fetched_at=datetime.now(timezone.utc), stale=False
        )

    def mark_stale(self, symbol: str, asset_class: AssetClass):
        """Called when a poll cycle fails to get fresh data for a symbol
        that's already cached — keep serving the old value, just flag it."""
        existing = self._store.get((asset_class, symbol))
        if existing:
            existing.stale = True

    def all_symbols(self) -> list[str]:
        return [symbol for _, symbol in self._store.keys()]


# Module-level singleton — simplest possible shared state for a single-
# process app. Swap for a proper DI container if this grows past a hackathon.
quote_cache = QuoteCache()
