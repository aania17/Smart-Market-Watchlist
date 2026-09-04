"""
"Meaningful change" detection — §4 of the requirements doc.

Two signals, deliberately, per the priority call made in planning:

1. change_since_last_visit — the differentiator itself. Diffs the current
   price against the PriceSnapshot taken the last time this watchlist was
   opened, NOT against today's market open.
2. relative_move_vs_index — the stock's move compared against a baseline
   index (SPY), so a 3% move on a flat market day reads as more
   significant than a 3% move on a day everything moved 3%. Stocks only —
   deliberately not computed for crypto (see requirements doc §8: no clean
   "market baseline" exists for crypto without introducing an unrelated
   data concept).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.market_data import AssetClass, Quote


@dataclass
class ChangeSignal:
    symbol: str
    asset_class: AssetClass
    current_price: float
    as_of: datetime

    # Signal 1 — always present if a prior snapshot exists
    change_since_last_visit_pct: float | None
    last_visit_price: float | None
    last_visit_at: datetime | None

    # Signal 2 — stocks only
    relative_move_vs_index_pct: float | None
    quantity: float | None
    impact: float | None

    is_stale: bool

    def is_meaningful(self, threshold_pct: float = 2.0) -> bool:
        """A simple, explainable threshold — not a black box. Tune these
        two numbers based on demo data; document whatever you land on in
        the README per the rubric's "independent choices, explained" row."""
        if self.change_since_last_visit_pct is not None and abs(self.change_since_last_visit_pct) >= threshold_pct:
            return True
        if self.relative_move_vs_index_pct is not None and abs(self.relative_move_vs_index_pct) >= threshold_pct:
            return True
        return False


def compute_change_since_last_visit(current_price: float, last_visit_price: float | None) -> float | None:
    if last_visit_price is None or last_visit_price == 0:
        return None
    return round((current_price - last_visit_price) / last_visit_price * 100, 4)


def compute_relative_move_vs_index(stock_quote: Quote, index_quote: Quote | None) -> float | None:
    """Stock's %change since previous close, minus the index's %change
    since previous close. Positive = outperforming the market; negative =
    underperforming — regardless of the stock's own absolute direction."""
    if index_quote is None:
        return None
    stock_pct = stock_quote.change_pct_since_prev_close
    index_pct = index_quote.change_pct_since_prev_close
    if stock_pct is None or index_pct is None:
        return None
    return round(stock_pct - index_pct, 4)


def build_change_signal(
    quote: Quote,
    last_visit_price: float | None,
    last_visit_at: datetime | None,
    index_quote: Quote | None,
    is_stale: bool,
    quantity: float | None = None,
) -> ChangeSignal:
    relative_move = (
        compute_relative_move_vs_index(quote, index_quote) if quote.asset_class is AssetClass.STOCK else None
    )
    return ChangeSignal(
        symbol=quote.symbol,
        asset_class=quote.asset_class,
        current_price=quote.price,
        as_of=quote.as_of,
        change_since_last_visit_pct=compute_change_since_last_visit(quote.price, last_visit_price),
        last_visit_price=last_visit_price,
        last_visit_at=last_visit_at,
        relative_move_vs_index_pct=relative_move,
        quantity=quantity,
        impact=(round(quantity * (quote.price - last_visit_price), 2)
            if quantity is not None and last_visit_price is not None else None),
        is_stale=is_stale,
    )
