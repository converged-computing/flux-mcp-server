import os

from .interface import DatabaseBackend
from .views import SQLAlchemyBackend

DATABASE: DatabaseBackend = None


def get_db() -> DatabaseBackend:
    global DATABASE
    if DATABASE:
        return DATABASE

    db_type = os.environ.get("FLUX_MCP_DATABASE_TYPE", "sqlite")

    if db_type == "sqlite":
        # Format: sqlite+aiosqlite:///path/to/db
        path = os.environ.get("FLUX_MCP_DATABASE_PATH", "flux-mcp-server-state.db")
        url = f"sqlite+aiosqlite:///{path}"

    elif db_type == "postgres":
        # Format: postgresql+asyncpg://user:pass@host/db
        dsn = os.environ.get("FLUX_MCP_DATABASE_DSN")
        # Ensure it starts with postgresql+asyncpg
        if dsn and not dsn.startswith("postgresql+asyncpg"):
            url = f"postgresql+asyncpg://{dsn}"
        else:
            url = dsn

    elif db_type in ["mariadb", "mysql"]:
        # Format: mysql+aiomysql://user:pass@host/db
        dsn = os.environ.get("FLUX_MCP_DATABASE_DSN")
        url = f"mysql+aiomysql://{dsn}"

    else:
        raise ValueError(f"Unknown DB type: {db_type}")

    DATABASE = SQLAlchemyBackend(url)
    return DATABASE
