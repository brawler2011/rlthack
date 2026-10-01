from collections.abc import Iterator

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import settings

# The pool is opened on app startup (lifespan) without waiting for the database:
# the API starts even while PostgreSQL is still booting, requests wait for a connection.
pool = ConnectionPool(
    settings.database_url,
    min_size=1,
    max_size=10,
    timeout=10,
    open=False,
    kwargs={"row_factory": dict_row},
)


def open_db():
    pool.open(wait=False)


def close_db():
    pool.close()


def get_db() -> Iterator[Connection]:
    """FastAPI dependency: a pooled connection for the request, rows as dicts."""
    with pool.connection() as conn:
        yield conn
