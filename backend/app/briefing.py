from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.change_detection import ChangeSignal


@dataclass
class MoveGroup:
    direction: str
    symbols: list[str]
    average_move_pct: float


def build_move_groups(signals: list[ChangeSignal], threshold_pct: float) -> list[MoveGroup]:
    candidates = [
        signal
        for signal in signals
        if signal.is_meaningful(threshold_pct)
        and not signal.is_stale
        and signal.change_since_last_visit_pct is not None
    ]
    groups: list[MoveGroup] = []
    for direction in ("up", "down"):
        selected = [
            signal for signal in candidates
            if (signal.change_since_last_visit_pct > 0) == (direction == "up")
        ]
        if len(selected) < 2:
            continue
        selected.sort(key=lambda signal: abs(signal.change_since_last_visit_pct or 0))
        buckets: list[list[ChangeSignal]] = []
        for signal in selected:
            move = abs(signal.change_since_last_visit_pct or 0)
            bucket = next(
                (bucket for bucket in buckets if abs(move - abs(bucket[0].change_since_last_visit_pct or 0)) <= 1.0),
                None,
            )
            if bucket is None:
                buckets.append([signal])
            else:
                bucket.append(signal)
        for bucket in buckets:
            if len(bucket) >= 2:
                average = round(sum(signal.change_since_last_visit_pct or 0 for signal in bucket) / len(bucket), 2)
                groups.append(MoveGroup(direction, [signal.symbol for signal in bucket], average))
    return groups


def build_briefing(signals: list[ChangeSignal], last_visit_at: datetime | None, threshold_pct: float) -> str:
    meaningful = [signal for signal in signals if signal.is_meaningful(threshold_pct)]
    if not meaningful:
        return "Nothing has moved enough to deserve your attention since your last visit."
    lead = max(meaningful, key=lambda signal: abs(signal.change_since_last_visit_pct or signal.relative_move_vs_index_pct or 0))
    move = lead.change_since_last_visit_pct
    move_text = f"{abs(move):.1f}% {'up' if move >= 0 else 'down'}" if move is not None else "a meaningful move"
    visit_text = "your last visit" if last_visit_at is None else f"{last_visit_at.strftime('%I:%M %p').lstrip('0')} UTC"
    outperformers = [signal for signal in meaningful if (signal.relative_move_vs_index_pct or 0) >= threshold_pct]
    market_text = f" {outperformers[0].symbol} is outperforming the index." if outperformers else ""
    return f"Since {visit_text}, {len(meaningful)} {('holding has' if len(meaningful) == 1 else 'holdings have')} moved meaningfully. {lead.symbol} is {move_text}.{market_text}"