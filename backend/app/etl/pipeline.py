"""Загрузка CSV в PostgreSQL и сборка витрин: общий код скриптов 01 и 02."""

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
    # Агрегации по миллионам строк и построение индексов без сброса на диск
    conn.execute("SET work_mem = '256MB'")
    conn.execute("SET maintenance_work_mem = '512MB'")
    return conn


@contextmanager
def timed(label: str) -> Iterator[None]:
    print(f">>> {label}...", flush=True)
    start = time.perf_counter()
    yield
    print(f"    готово за {time.perf_counter() - start:.1f} с", flush=True)


def run_sql_file(conn: psycopg.Connection, name: str) -> None:
    conn.execute((SQL_DIR / name).read_text(encoding="utf-8"))


def load_raw(conn: psycopg.Connection, sources: dict[str, list[RawFile]]) -> None:
    """Копирует CSV как есть в staging-таблицы stg_<тип>, все колонки — text."""
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
    "Строк извещений в CSV": "SELECT count(*) FROM stg_notices",
    "Лотов после очистки": "SELECT count(*) FROM lots",
    "Строк ТРУ в CSV": "SELECT count(*) FROM stg_items",
    "Позиций ТРУ после очистки": "SELECT count(*) FROM lot_items",
    "Позиций ТРУ без корректного ОКПД2": "SELECT count(*) FROM lot_items WHERE okpd2_code IS NULL",
    "Строк участий в CSV": "SELECT count(*) FROM stg_bids",
    "Участий после очистки (пары лот–ИНН)": "SELECT count(*) FROM bids",
    "Участий с некорректным ИНН": (
        "SELECT count(*) FROM stg_bids WHERE clean_inn(supplier_inn) IS NULL"
    ),
    "Уникальных поставщиков": "SELECT count(DISTINCT supplier_inn) FROM bids",
    "Участий в лотах, которых нет в извещениях": (
        "SELECT count(*) FROM bids b "
        "WHERE NOT EXISTS (SELECT 1 FROM lots l WHERE l.lot_id = b.lot_id)"
    ),
    "Лотов без участников": (
        "SELECT count(*) FROM lots l "
        "WHERE NOT EXISTS (SELECT 1 FROM bids b WHERE b.lot_id = l.lot_id)"
    ),
    "Лотов без позиций ТРУ": (
        "SELECT count(*) FROM lots l "
        "WHERE NOT EXISTS (SELECT 1 FROM lot_items i WHERE i.lot_id = l.lot_id)"
    ),
    "Лотов с участниками, но без победителя": (
        "SELECT count(*) FROM (SELECT lot_id FROM bids GROUP BY lot_id "
        "HAVING NOT bool_or(is_winner)) s"
    ),
    "Лотов с несколькими победителями": (
        "SELECT count(*) FROM (SELECT lot_id FROM bids GROUP BY lot_id "
        "HAVING count(*) FILTER (WHERE is_winner) > 1) s"
    ),
}


def load_report(conn: psycopg.Connection) -> dict[str, int]:
    return {label: conn.execute(query).fetchone()[0] for label, query in REPORT_QUERIES.items()}


def channel_report(conn: psycopg.Connection) -> list[tuple]:
    """Пустые поля извещений в разрезе АИС ГЗ / электронный магазин."""
    return conn.execute(
        """
        SELECT
            coalesce(channel, '(пусто)'),
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
