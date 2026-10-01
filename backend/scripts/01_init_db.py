"""Скрипт 01: пересоздание схемы PostgreSQL и загрузка исходных CSV (~4.5M строк)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.etl import pipeline  # noqa: E402
from app.etl.sources import detect_sources  # noqa: E402


def main():
    sources = detect_sources(settings.raw_data_dir)
    print(f">>> [01] Исходные файлы в {settings.raw_data_dir}:")
    for files in sources.values():
        for raw in files:
            fmt = f"{raw.encoding}, разделитель {raw.delimiter!r}"
            print(f"    {raw.kind:8} {raw.path.name}  ({fmt})")

    with pipeline.connect() as conn:
        with pipeline.timed("[01] Схема"):
            pipeline.run_sql_file(conn, "schema.sql")
        with pipeline.timed("[01] Загрузка CSV в staging"):
            pipeline.load_raw(conn, sources)
        with pipeline.timed("[01] Очистка в lots, lot_items, bids"):
            pipeline.run_sql_file(conn, "clean.sql")
        conn.commit()

        print(">>> [01] Отчёт о загрузке:")
        for label, value in pipeline.load_report(conn).items():
            print(f"    {label}: {value:_}".replace("_", " "))

        print(
            ">>> [01] Извещения по каналам "
            "(всего / без ИНН заказчика / без реестр. номера / без НМЦК):"
        )
        for channel, total, no_customer, no_reqnum, no_price in pipeline.channel_report(conn):
            print(f"    {channel}: {total} / {no_customer} / {no_reqnum} / {no_price}")


if __name__ == "__main__":
    main()
