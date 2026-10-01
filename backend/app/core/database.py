from collections.abc import Iterator

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import settings

# Пул открывается при старте приложения (lifespan) без ожидания базы:
# API поднимается, даже если PostgreSQL ещё стартует, а запросы подождут соединение.
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
    """FastAPI-зависимость: соединение из пула на время запроса, строки — словари."""
    with pool.connection() as conn:
        yield conn
