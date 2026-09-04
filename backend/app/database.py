from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

# SQLAlchemy needs an explicit psycopg driver when psycopg3 is installed.
# Supabase supplies either `postgres://` or `postgresql://` URLs, so normalize
# both forms while leaving SQLite untouched for local fallback development.
database_url = settings.DATABASE_URL
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

# check_same_thread only matters for SQLite.
connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}

engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_schema_compatibility() -> None:
    """Apply the small additive upgrades needed by existing SQLite databases."""
    if not settings.DATABASE_URL.startswith("sqlite"):
        return
    inspector = inspect(engine)
    with engine.begin() as connection:
        watchlist_columns = {column["name"] for column in inspector.get_columns("watchlists")}
        if "meaningful_threshold_pct" not in watchlist_columns:
            connection.execute(
                text("ALTER TABLE watchlists ADD COLUMN meaningful_threshold_pct FLOAT NOT NULL DEFAULT 2.0")
            )
        item_columns = {column["name"] for column in inspector.get_columns("watchlist_items")}
        if "quantity" not in item_columns:
            connection.execute(text("ALTER TABLE watchlist_items ADD COLUMN quantity FLOAT"))


def get_db():
    """FastAPI dependency — yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
