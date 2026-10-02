"""Script 09: Names of suppliers outside the SME registry (large companies, state institutions).

Loads resources/organizations.csv into the organizations table; the API shows these names where
the SME registry has none. --build rebuilds the file: every supplier from the bids that is not
in the registry is looked up in the public EGRUL search (egrul.nalog.ru), a few requests a second.
"""

import argparse
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.etl import pipeline  # noqa: E402

RESOURCE = Path(__file__).resolve().parent.parent / "resources" / "organizations.csv"
FIELDS = ("inn", "name", "full_name", "registered", "source")
EGRUL = "https://egrul.nalog.ru/"
MISSING_SQL = """
SELECT DISTINCT b.supplier_inn FROM bids b
LEFT JOIN companies c ON c.inn = b.supplier_inn
WHERE c.inn IS NULL
ORDER BY 1
"""


def egrul(inn: str) -> dict | None:
    """Short and full name and registration date of a company or sole trader by INN."""
    headers = {"User-Agent": "Mozilla/5.0"}
    for attempt in range(5):
        try:
            query = urllib.parse.urlencode({"query": inn, "region": "", "page": ""}).encode()
            with urllib.request.urlopen(urllib.request.Request(EGRUL, query, headers), 30) as r:
                token = json.load(r)
            if token.get("captchaRequired"):
                time.sleep(30)
                continue
            time.sleep(0.7)
            url = f"{EGRUL}search-result/{token['t']}"
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), 30) as r:
                rows = [row for row in json.load(r).get("rows", []) if row.get("i") == inn]
            time.sleep(0.5)
            if not rows:
                return None
            row = rows[0]
            registered = datetime.strptime(row["r"], "%d.%m.%Y").date() if row.get("r") else None
            return {
                "inn": inn,
                "name": row.get("c") or row.get("n"),
                "full_name": row.get("n"),
                "registered": registered,
                "source": "egrul",
            }
        except (OSError, ValueError, KeyError):
            time.sleep(5 * (attempt + 1))
    return None


def build(path: Path) -> None:
    with pipeline.connect() as conn:
        inns = [r[0] for r in conn.execute(MISSING_SQL).fetchall()]
    print(f"    suppliers outside the SME registry: {len(inns)}")
    with ThreadPoolExecutor(4) as pool:
        found = [o for o in pool.map(egrul, inns) if o is not None]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, FIELDS, delimiter=";")
        writer.writeheader()
        writer.writerows(found)
    print(f"    found in EGRUL: {len(found)}, saved to {path}")


def load(path: Path) -> None:
    with pipeline.connect() as conn:
        pipeline.run_sql_file(conn, "organizations_schema.sql")
        with path.open(encoding="utf-8", newline="") as f, conn.cursor() as cur:
            rows = csv.DictReader(f, delimiter=";")
            with cur.copy("COPY organizations FROM STDIN") as copy:
                for r in rows:
                    copy.write_row([r[k] or None for k in FIELDS])
        count = conn.execute("SELECT count(*) FROM organizations").fetchone()[0]
        conn.commit()
    print(f"    organizations: {count}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=RESOURCE)
    parser.add_argument("--build", action="store_true", help="look the names up in EGRUL first")
    args = parser.parse_args()
    if args.build:
        with pipeline.timed("[09] Looking suppliers up in EGRUL"):
            build(args.file)
    with pipeline.timed("[09] Loading organizations"):
        load(args.file)


if __name__ == "__main__":
    main()
