"""Load CSVs into PostgreSQL and build marts: shared code of scripts 01 and 02."""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg import sql

from app.config import settings
from app.etl.sources import RawFile

SQL_DIR = Path(__file__).parent / "sql"
COPY_CHUNK = 1 << 20


def connect(url: str | None = None) -> psycopg.Connection:
    conn = psycopg.connect(url or settings.database_url)
    # Aggregations over millions of rows and index builds without spilling to disk
    conn.execute("SET work_mem = '256MB'")
    conn.execute("SET maintenance_work_mem = '512MB'")
    return conn


@contextmanager
def timed(label: str) -> Iterator[None]:
    print(f">>> {label}...", flush=True)
    start = time.perf_counter()
    yield
    print(f"    done in {time.perf_counter() - start:.1f} s", flush=True)


def run_sql_file(conn: psycopg.Connection, name: str) -> None:
    conn.execute((SQL_DIR / name).read_text(encoding="utf-8"))


def load_raw(conn: psycopg.Connection, sources: dict[str, list[RawFile]]) -> None:
    """Copy CSVs as is into staging tables stg_<kind>, all columns text."""
    for kind, files in sources.items():
        table = sql.Identifier(f"stg_{kind}")
        columns = list(dict.fromkeys(c for f in files for c in f.columns))
        conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(table))
        conn.execute(
            sql.SQL("CREATE UNLOGGED TABLE {} ({})").format(
                table,
                sql.SQL(", ").join(sql.SQL("{} text").format(sql.Identifier(c)) for c in columns),
            )
        )
        for raw in files:
            copy_csv(conn, table, raw)


def copy_csv(conn: psycopg.Connection, table: sql.Identifier, raw: RawFile) -> None:
    stmt = sql.SQL(
        "COPY {} ({}) FROM STDIN WITH (FORMAT csv, HEADER true, DELIMITER {}, ENCODING {})"
    ).format(
        table,
        sql.SQL(", ").join(map(sql.Identifier, raw.columns)),
        sql.Literal(raw.delimiter),
        sql.Literal(raw.pg_encoding),
    )
    with conn.cursor() as cur, cur.copy(stmt) as copy, raw.path.open("rb") as f:
        while chunk := f.read(COPY_CHUNK):
            copy.write(chunk)


REPORT_QUERIES = {
    "Notice rows in CSV": "SELECT count(*) FROM stg_notices",
    "Lots after cleaning": "SELECT count(*) FROM lots",
    "TRU rows in CSV": "SELECT count(*) FROM stg_items",
    "TRU items after cleaning": "SELECT count(*) FROM lot_items",
    "TRU items without a valid OKPD2": "SELECT count(*) FROM lot_items WHERE okpd2_code IS NULL",
    "Bid rows in CSV": "SELECT count(*) FROM stg_bids",
    "Bids after cleaning (lot-INN pairs)": "SELECT count(*) FROM bids",
    "Bids with an invalid INN": (
        "SELECT count(*) FROM stg_bids WHERE clean_inn(supplier_inn) IS NULL"
    ),
    "Distinct suppliers": "SELECT count(DISTINCT supplier_inn) FROM bids",
    "Bids on lots missing from notices": (
        "SELECT count(*) FROM bids b "
        "WHERE NOT EXISTS (SELECT 1 FROM lots l WHERE l.lot_id = b.lot_id)"
    ),
    "Lots without bids": (
        "SELECT count(*) FROM lots l "
        "WHERE NOT EXISTS (SELECT 1 FROM bids b WHERE b.lot_id = l.lot_id)"
    ),
    "Lots without TRU items": (
        "SELECT count(*) FROM lots l "
        "WHERE NOT EXISTS (SELECT 1 FROM lot_items i WHERE i.lot_id = l.lot_id)"
    ),
    "Lots with bids but no winner": (
        "SELECT count(*) FROM (SELECT lot_id FROM bids GROUP BY lot_id "
        "HAVING NOT bool_or(is_winner)) s"
    ),
    "Lots with several winners": (
        "SELECT count(*) FROM (SELECT lot_id FROM bids GROUP BY lot_id "
        "HAVING count(*) FILTER (WHERE is_winner) > 1) s"
    ),
}


def load_report(conn: psycopg.Connection) -> dict[str, int]:
    return {label: conn.execute(query).fetchone()[0] for label, query in REPORT_QUERIES.items()}


def channel_report(conn: psycopg.Connection) -> list[tuple]:
    """Empty notice fields per channel (AIS GZ / e-shop)."""
    return conn.execute(
        """
        SELECT
            coalesce(channel, '(empty)'),
            count(*),
            count(*) FILTER (WHERE customer_inn IS NULL),
            count(*) FILTER (WHERE reqnum IS NULL),
            count(*) FILTER (WHERE start_price IS NULL)
        FROM lots
        GROUP BY 1
        ORDER BY 2 DESC
        """
    ).fetchall()


MART_TABLES = ("supplier_profile", "supplier_okpd2", "supplier_customer", "supplier_text")


def mart_sizes(conn: psycopg.Connection) -> dict[str, int]:
    return {
        table: conn.execute(
            sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
        ).fetchone()[0]
        for table in MART_TABLES
    }
