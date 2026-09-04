"""
SQLAlchemy models for the Smart Market Watchlist.

Design notes (see the requirements doc, §5 and §6, for the reasoning):
- `Watchlist.last_viewed_at` is the server-side "when did the user last
  check" timestamp §4.1 diffs against — deliberately per-watchlist, not
  per-symbol, as the simpler default.
- `PriceSnapshot` rows are the "price as of last acknowledged visit" record
  for each symbol in a watchlist, refreshed only when the user acknowledges
  the current changes.
- Live/current prices are NOT stored here — those come from the in-memory
  cache in market_data_cache.py, refreshed by the background poller. This
  table only holds the "last visit" baseline, which is durable and must
  survive server restarts.
"""
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Float, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    watchlists = relationship("Watchlist", back_populates="owner", cascade="all, delete-orphan")


class Watchlist(Base):
    __tablename__ = "watchlists"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    name = Column(String, nullable=False, default="My Watchlist")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    # The §5 "state persistence" field — updated every time the user opens
    # this watchlist. Nullable because a brand-new watchlist has never been
    # viewed, so there's nothing to diff against yet.
    last_viewed_at = Column(DateTime, nullable=True)
    meaningful_threshold_pct = Column(Float, nullable=False, default=2.0)

    owner = relationship("User", back_populates="watchlists")
    items = relationship("WatchlistItem", back_populates="watchlist", cascade="all, delete-orphan")
    snapshots = relationship("PriceSnapshot", back_populates="watchlist", cascade="all, delete-orphan")


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("watchlist_id", "symbol", name="uq_watchlist_symbol"),)

    id = Column(Integer, primary_key=True, index=True)
    watchlist_id = Column(Integer, ForeignKey("watchlists.id"), index=True, nullable=False)
    symbol = Column(String, nullable=False)  # e.g. "AAPL" or "BTC/USD"
    asset_class = Column(String, nullable=False)  # "stock" | "crypto" — see app.market_data.AssetClass
    quantity = Column(Float, nullable=True)
    added_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    watchlist = relationship("Watchlist", back_populates="items")


class PriceSnapshot(Base):
    """
    The price of `symbol` the last time `watchlist` was viewed — this is
    what §4.1 ("change since last visit") diffs the current price against.
    One row per (watchlist, symbol), overwritten on each view.
    """
    __tablename__ = "price_snapshots"
    __table_args__ = (UniqueConstraint("watchlist_id", "symbol", name="uq_snapshot_watchlist_symbol"),)

    id = Column(Integer, primary_key=True, index=True)
    watchlist_id = Column(Integer, ForeignKey("watchlists.id"), index=True, nullable=False)
    symbol = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    captured_at = Column(DateTime, nullable=False)

    watchlist = relationship("Watchlist", back_populates="snapshots")
