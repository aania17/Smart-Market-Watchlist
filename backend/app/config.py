"""
App configuration, loaded from environment variables (.env in dev).
Change PROJECT_NAME / SECRET_KEY / DB URL here or via env vars — nothing
else in the codebase should hardcode config.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "Hackathon Starter"
    SECRET_KEY: str = "change-me-before-you-deploy"  # override via env var
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h — generous for a hackathon demo
    DATABASE_URL: str = "sqlite:///./app.db"
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]  # vite dev server

    # Alpaca Market Data API — https://alpaca.markets/ (free tier, no card)
    ALPACA_API_KEY: str = ""
    ALPACA_SECRET_KEY: str = ""
    ALPACA_DATA_BASE_URL: str = "https://data.alpaca.markets"
    INDEX_BASELINE_SYMBOL: str = "SPY"  # used for §4.2 relative-move calc
    QUOTE_POLL_INTERVAL_SECONDS: int = 45


settings = Settings()
