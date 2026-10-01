"""Script 01: Recreate the PostgreSQL schema and load the raw CSVs (~4.5M rows)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.etl import pipeline  # noqa: E402
from app.etl.sources import detect_sources  # noqa: E402


def main():
    sources = detect_sources(settings.raw_data_dir)
    print(f">>> [01] Source files in {settings.raw_data_dir}:")
    for files in sources.values():
        for raw in files:
            fmt = f"{raw.encoding}, delimiter {raw.delimiter!r}"
            print(f"    {raw.kind:8} {raw.path.name}  ({fmt})")

    with pipeline.connect() as conn:
        with pipeline.timed("[01] Schema"):
            pipeline.run_sql_file(conn, "schema.sql")
        with pipeline.timed("[01] Loading CSVs into staging"):
            pipeline.load_raw(conn, sources)
        with pipeline.timed("[01] Cleaning into lots, lot_items, bids"):
            pipeline.run_sql_file(conn, "clean.sql")
        conn.commit()

        print(">>> [01] Load report:")
        for label, value in pipeline.load_report(conn).items():
            print(f"    {label}: {value:_}".replace("_", " "))

        print(">>> [01] Notices by channel (total / no customer INN / no reqnum / no start price):")
        for channel, total, no_customer, no_reqnum, no_price in pipeline.channel_report(conn):
            print(f"    {channel}: {total} / {no_customer} / {no_reqnum} / {no_price}")


if __name__ == "__main__":
    main()
