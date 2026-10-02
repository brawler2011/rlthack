"""Script 03: Enrich suppliers from the FNS SME registry: names, OKVED, roles, new companies.

Keeps every company registered in Saint Petersburg or Leningrad Region (the pool of possible new
suppliers) plus every supplier from the procurement data, wherever it is registered.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.etl import pipeline, rmsp  # noqa: E402

REPORT = """
SELECT
    (SELECT count(DISTINCT supplier_inn) FROM bids),
    count(*) FILTER (WHERE in_history),
    count(*) FILTER (WHERE NOT in_history),
    count(*) FILTER (WHERE role = 'MANUFACTURER'),
    count(*) FILTER (WHERE role = 'DISTRIBUTOR'),
    count(*) FILTER (WHERE role = 'SUPPLIER'),
    count(*) FILTER (WHERE cardinality(products) > 0)
FROM companies
"""


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump", type=Path, default=settings.rmsp_dump_path)
    parser.add_argument("--download", action="store_true", help="fetch the newest dump first")
    parser.add_argument("--regions", default="78,47")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.download and not args.dump.exists():
        url = rmsp.latest_dump_url()
        with pipeline.timed(f"[03] Downloading {url}"):
            rmsp.download(url, args.dump)
    if not args.dump.exists():
        print(f">>> [03] No SME registry dump at {args.dump}: run with --download. Skipped.")
        return

    with pipeline.connect() as conn:
        inns = {row[0] for row in conn.execute("SELECT DISTINCT supplier_inn FROM bids")}
    with pipeline.timed(f"[03] Reading {args.dump.name}"):
        companies = {
            c.inn: c for c in rmsp.read_dump(args.dump, set(args.regions.split(",")), inns)
        }

    with pipeline.connect() as conn:
        with pipeline.timed(f"[03] Loading {len(companies)} companies"):
            pipeline.run_sql_file(conn, "companies_schema.sql")
            with conn.cursor() as cur, cur.copy("COPY companies FROM STDIN") as copy:
                for c in companies.values():
                    copy.write_row(
                        (
                            c.inn,
                            c.name,
                            c.is_individual,
                            c.region,
                            c.category,
                            c.headcount,
                            c.msp_since,
                            c.okved_main,
                            c.okved_main_name,
                            c.okved_extra,
                            c.products,
                            c.licenses,
                            "rmsp",
                            None,
                            None,
                            None,
                        )
                    )
            pipeline.run_sql_file(conn, "companies.sql")
        conn.commit()

        suppliers, found, new, made, wholesale, other, declared = conn.execute(REPORT).fetchone()
        print(
            f"    suppliers from the procurement data found in the registry: {found} of {suppliers}"
        )
        print(f"    new companies (no bids in the data): {new}")
        print(f"    roles: manufacturer {made}, distributor {wholesale}, supplier {other}")
        print(f"    companies declaring their own products: {declared}")


if __name__ == "__main__":
    main()
