from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, ConfigDict, Field, model_validator


# ---- Auth ----
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)
    full_name: str | None = Field(default=None, max_length=100)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None = None
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- Watchlist ----
class WatchlistCreate(BaseModel):
    name: str = Field(default="My Watchlist", min_length=1, max_length=100)

    @model_validator(mode="after")
    def name_must_not_be_blank(self):
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("name must not be blank")
        return self


class WatchlistOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    last_viewed_at: datetime | None = None
    meaningful_threshold_pct: float = 2.0


class SensitivityUpdate(BaseModel):
    meaningful_threshold_pct: float = Field(ge=0.1, le=20.0)


class WatchlistItemCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)  # "AAPL" for stocks, "BTC/USD" for crypto
    asset_class: Literal["stock", "crypto"]
    quantity: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_symbol(self):
        symbol = self.symbol.strip()
        if self.asset_class == "stock":
            symbol = symbol.upper()
            if not symbol.replace(".", "").replace("-", "").isalnum() or len(symbol) > 10:
                raise ValueError("stock symbol must be a valid ticker")
        elif self.asset_class == "crypto":
            symbol = symbol.upper()
            parts = symbol.split("/")
            if len(parts) != 2 or not all(part.isalnum() for part in parts):
                raise ValueError("crypto symbol must use BASE/QUOTE format")
        else:
            raise ValueError("asset_class must be 'stock' or 'crypto'")
        self.symbol = symbol
        return self


class WatchlistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    asset_class: str
    added_at: datetime
    quantity: float | None = None


class QuantityUpdate(BaseModel):
    quantity: float | None = Field(default=None, gt=0)


# ---- Change signal (the "what's meaningfully changed" view) ----
class ChangeSignalOut(BaseModel):
    symbol: str
    asset_class: str
    current_price: float
    as_of: datetime
    change_since_last_visit_pct: float | None
    last_visit_price: float | None
    last_visit_at: datetime | None
    relative_move_vs_index_pct: float | None
    quantity: float | None
    impact: float | None
    is_stale: bool
    is_meaningful: bool


class MoveGroupOut(BaseModel):
    direction: Literal["up", "down"]
    symbols: list[str]
    average_move_pct: float


class WatchlistViewOut(BaseModel):
    """The main payload the frontend renders: the watchlist plus each
    item's current price and computed change signals."""
    watchlist: WatchlistOut
    items: list[WatchlistItemOut]
    signals: list[ChangeSignalOut]
    briefing: str
    move_groups: list[MoveGroupOut]


class HourlyPointOut(BaseModel):
    timestamp: datetime
    price: float


class HourlySeriesOut(BaseModel):
    symbol: str
    asset_class: str
    points: list[HourlyPointOut]
    change_pct: float | None = None
