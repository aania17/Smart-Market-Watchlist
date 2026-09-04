"""
Market data client — wraps the Alpaca Market Data API (free tier).

Single provider for both asset classes, deliberately: stocks (US equities,
IEX feed) and crypto share this module's interface so the rest of the app
(caching, "meaningful change" calculation) never has to branch on asset
class to fetch data — it only branches where the business logic actually
differs (see AssetClass usage in change_detection.py).

Docs used to build this:
- Stocks snapshots: GET /v2/stocks/snapshots?symbols=...
- Stocks historical bars: GET /v2/stocks/bars?symbols=...&timeframe=...
- Crypto snapshots: GET /v1beta3/crypto/us/snapshots?symbols=...
- Crypto historical bars: GET /v1beta3/crypto/us/bars?symbols=...&timeframe=...

If Alpaca ever changes these paths, this is the only file that needs to
change — nothing else in the app talks to the network directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

import httpx

from app.config import settings


class AssetClass(str, Enum):
    STOCK = "stock"
    CRYPTO = "crypto"


class MarketDataUnavailable(Exception):
    """Raised when the upstream API is unreachable entirely (network/auth
    failure) — as opposed to a single symbol simply missing from the
    response, which callers should treat as "no data for this symbol" and
    keep going, not fail the whole batch."""


@dataclass
class Quote:
    symbol: str
    asset_class: AssetClass
    price: float
    prev_close: float | None
    as_of: datetime  # when Alpaca says this price is from — surfaced to the
    # user as "as of HH:MM" per the requirements doc's stale-data honesty rule

    @property
    def change_pct_since_prev_close(self) -> float | None:
        if not self.prev_close:
            return None
        return round((self.price - self.prev_close) / self.prev_close * 100, 4)


@dataclass
class Bar:
    symbol: str
    close: float
    timestamp: datetime


class AlpacaClient:
    STOCK_BASE = "/v2/stocks"
    CRYPTO_BASE = "/v1beta3/crypto/us"

    def __init__(
        self,
        api_key: str = settings.ALPACA_API_KEY,
        secret_key: str = settings.ALPACA_SECRET_KEY,
        base_url: str = settings.ALPACA_DATA_BASE_URL,
        timeout_seconds: float = 5.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": secret_key,
        }

    def _get(self, path: str, params: dict) -> dict:
        try:
            resp = httpx.get(
                f"{self.base_url}{path}",
                headers=self._headers,
                params=params,
                timeout=self.timeout_seconds,
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            # Total failure to reach the provider — callers should fall back
            # to cached data, not crash the request. See §8 of requirements doc.
            raise MarketDataUnavailable(str(exc)) from exc

    # ---------------- Snapshots (current price) ----------------
    def get_snapshots(self, symbols: list[str], asset_class: AssetClass) -> dict[str, Quote]:
        """Fetch latest price + previous close for a batch of symbols in one
        request. Missing symbols are simply absent from the returned dict —
        callers should treat that as "no data," not an error."""
        if not symbols:
            return {}

        if asset_class is AssetClass.STOCK:
            data = self._get(f"{self.STOCK_BASE}/snapshots", {"symbols": ",".join(symbols), "feed": "iex"})
        else:
            data = self._get(f"{self.CRYPTO_BASE}/snapshots", {"symbols": ",".join(symbols)})

        quotes: dict[str, Quote] = {}
        # Stock snapshots are returned as a symbol-keyed object directly;
        # crypto snapshots use the nested `snapshots` envelope.
        snapshots = data.get("snapshots") if asset_class is AssetClass.CRYPTO else data
        for symbol, snap in (snapshots or {}).items():
            latest_trade = snap.get("latestTrade") or {}
            prev_daily_bar = snap.get("prevDailyBar") or {}
            price = latest_trade.get("p")
            if price is None:
                continue  # no trade data yet for this symbol — skip, don't fabricate
            as_of_raw = latest_trade.get("t")
            as_of = _parse_timestamp(as_of_raw) if as_of_raw else datetime.now(timezone.utc)
            quotes[symbol] = Quote(
                symbol=symbol,
                asset_class=asset_class,
                price=float(price),
                prev_close=prev_daily_bar.get("c"),
                as_of=as_of,
            )
        return quotes

    # ---------------- Historical bars (for local caching / catch-up math) ----------------
    def get_daily_bars(
        self, symbols: list[str], asset_class: AssetClass, start: datetime, end: datetime
    ) -> dict[str, list[Bar]]:
        """Fetch daily close history for a batch of symbols — fetched once
        and cached in our own DB (see PriceSnapshot), not re-fetched on
        every request."""
        if not symbols:
            return {}

        params = {
            "symbols": ",".join(symbols),
            "timeframe": "1Day",
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
        if asset_class is AssetClass.STOCK:
            data = self._get(f"{self.STOCK_BASE}/bars", {**params, "feed": "iex"})
        else:
            data = self._get(f"{self.CRYPTO_BASE}/bars", params)

        result: dict[str, list[Bar]] = {}
        for symbol, bars in (data.get("bars") or {}).items():
            result[symbol] = [
                Bar(symbol=symbol, close=b["c"], timestamp=_parse_timestamp(b["t"])) for b in bars
            ]
        return result

    def get_hourly_bars(
        self, symbols: list[str], asset_class: AssetClass, start: datetime, end: datetime
    ) -> dict[str, list[Bar]]:
        """Fetch hourly close history for a compact intraday watchlist view."""
        if not symbols:
            return {}

        params = {
            "symbols": ",".join(symbols),
            "timeframe": "1Hour",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "limit": 24,
        }
        if asset_class is AssetClass.STOCK:
            data = self._get(f"{self.STOCK_BASE}/bars", {**params, "feed": "iex"})
        else:
            data = self._get(f"{self.CRYPTO_BASE}/bars", params)

        return {
            symbol: [Bar(symbol=symbol, close=b["c"], timestamp=_parse_timestamp(b["t"])) for b in bars]
            for symbol, bars in (data.get("bars") or {}).items()
        }


def _parse_timestamp(raw: str) -> datetime:
    # Alpaca returns RFC-3339 timestamps like "2026-09-04T14:30:00.123456789Z"
    # — Python's fromisoformat chokes on the trailing "Z" and nanosecond
    # precision, so normalize before parsing.
    cleaned = raw.replace("Z", "+00:00")
    if "." in cleaned:
        head, _, tail = cleaned.partition(".")
        frac, _, offset = tail.partition("+")
        cleaned = f"{head}.{frac[:6]}+{offset}"  # truncate to microseconds
    return datetime.fromisoformat(cleaned)
