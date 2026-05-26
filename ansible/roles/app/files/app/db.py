"""PostgreSQL connection pool management.

A small connection pool is created once at application start-up and reused
for every request. Rows are returned as dictionaries for convenience.
"""

from __future__ import annotations

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import Config, dsn

_pool: ConnectionPool | None = None


def init_pool(config: Config) -> ConnectionPool:
    """Create the global connection pool (idempotent)."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=dsn(config.database),
            min_size=1,
            max_size=4,
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return _pool


def get_pool() -> ConnectionPool:
    """Return the initialised pool or fail loudly if start-up was skipped."""
    if _pool is None:
        raise RuntimeError("Connection pool has not been initialised")
    return _pool


def close_pool() -> None:
    """Close the pool on application shutdown."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
