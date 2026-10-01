"""Script 02: Build supplier marts (WinRate, average check, OKPD2/customer history, TRU text)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.etl import pipeline  # noqa: E402


def main():
    with pipeline.connect() as conn:
        with pipeline.timed("[02] Building supplier marts"):
            pipeline.run_sql_file(conn, "marts.sql")
        conn.commit()

        for table, rows in pipeline.mart_sizes(conn).items():
            print(f"    {table}: " + f"{rows:_}".replace("_", " "))


if __name__ == "__main__":
    main()
