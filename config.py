import os

def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./aircraft.db")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url

DATABASE_URL = _database_url()
# Comma-separated origins allowed to call the API (the tool's GitHub Pages / Railway URL).
# "*" is the default since the data is non-sensitive and access is intentionally open.
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
