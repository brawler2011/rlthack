"""Скрипт 02: витрины поставщиков (WinRate, средний чек, опыт по ОКПД2 и заказчикам, тексты ТРУ)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.etl import pipeline  # noqa: E402


def main():
    with pipeline.connect() as conn:
        with pipeline.timed("[02] Сборка витрин поставщиков"):
            pipeline.run_sql_file(conn, "marts.sql")
        conn.commit()

        for table, rows in pipeline.mart_sizes(conn).items():
            print(f"    {table}: {rows:_}".replace("_", " "))


if __name__ == "__main__":
    main()
