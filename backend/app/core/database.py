import duckdb

from app.config import settings

_db_conn = None


def get_db():
    """Get DuckDB connection (Read-Only for multithreaded API)."""
    global _db_conn
    if _db_conn is None:
        if settings.duckdb_path.exists():
            _db_conn = duckdb.connect(str(settings.duckdb_path), read_only=True)
        else:
            _db_conn = duckdb.connect(":memory:")
    return _db_conn


def close_db():
    global _db_conn
    if _db_conn is not None:
        _db_conn.close()
        _db_conn = None
