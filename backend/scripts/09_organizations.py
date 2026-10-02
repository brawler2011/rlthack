"""Script 09: Open FNS data about suppliers: names, OKVED, status, revenue, taxes, tax debt.

Loads resources/organizations.csv into the organizations table. The API shows names and roles
of suppliers outside the SME registry (large companies, state institutions) and reliability
warnings next to the recommendations.

--build rebuilds the file (needs the internet, about an hour):
  * names and registration dates from the public EGRUL search (egrul.nalog.ru) and OKVED, status
    and revenue from the accounting statements registry (bo.nalog.gov.ru), for the suppliers
    outside the SME registry, a few requests a second;
  * with --fns-dir: revenue and expenses (revexp), taxes paid (paytax), tax debt (debtam) and
    headcount (sshr2019) of every supplier, from the FNS open data zips in that directory
    (https://www.nalog.gov.ru/opendata/7707329152-<name>/).
"""

import argparse
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.etl import pipeline  # noqa: E402

RESOURCE = Path(__file__).resolve().parent.parent / "resources" / "organizations.csv"
FIELDS = (
    "inn",
    "name",
    "full_name",
    "registered",
    "okved",
    "status",
    "revenue",
    "expenses",
    "taxes_paid",
    "tax_debt",
    "headcount",
    "source",
)
HEADERS = {"User-Agent": "Mozilla/5.0"}
SUPPLIERS_SQL = """
SELECT b.supplier_inn, c.inn IS NOT NULL FROM (SELECT DISTINCT supplier_inn FROM bids) b
LEFT JOIN companies c ON c.inn = b.supplier_inn
"""
_DOC = re.compile(r"<Документ\b.*?</Документ>", re.S)
_INN = re.compile(r'ИННЮЛ="(\d{10})"')


def _get(url: str, data: bytes | None = None):
    for attempt in range(5):
        try:
            request = urllib.request.Request(url, data, HEADERS)
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except (OSError, ValueError):
            time.sleep(5 * (attempt + 1))
    return None


def egrul(inn: str) -> dict:
    """Short and full name and registration date from the public EGRUL search."""
    query = urllib.parse.urlencode({"query": inn, "region": "", "page": ""}).encode()
    token = _get("https://egrul.nalog.ru/", query)
    if not token or token.get("captchaRequired"):
        return {}
    time.sleep(0.7)
    found = _get(f"https://egrul.nalog.ru/search-result/{token['t']}") or {}
    row = next((r for r in found.get("rows", []) if r.get("i") == inn), None)
    time.sleep(0.5)
    if not row:
        return {}
    registered = datetime.strptime(row["r"], "%d.%m.%Y").date() if row.get("r") else None
    return {
        "name": row.get("c") or row.get("n"),
        "full_name": row.get("n"),
        "registered": registered,
    }


def statements(inn: str) -> dict:
    """OKVED, status and revenue from the accounting statements registry."""
    url = f"https://bo.nalog.gov.ru/advanced-search/organizations/search?query={inn}&page=0"
    found = _get(url) or {}
    time.sleep(0.4)
    row = next(
        (r for r in found.get("content", []) if re.sub(r"<[^>]+>", "", r.get("inn") or "") == inn),
        None,
    )
    if not row:
        return {}
    gain = (row.get("bfo") or {}).get("gainSum")  # thousands of rubles
    return {
        "name": row.get("shortName"),
        "okved": row.get("okved2"),
        "status": row.get("statusCode"),
        "revenue": gain * 1000 if gain is not None else None,
    }


def fns_open_data(directory: Path, inns: set[str]) -> dict[str, dict]:
    data: dict[str, dict] = defaultdict(dict)

    def scan(name, handle):
        with zipfile.ZipFile(directory / name) as z:
            for member in z.namelist():
                for doc in _DOC.findall(z.read(member).decode("utf-8", "ignore")):
                    if (inn := _INN.search(doc)) and inn.group(1) in inns:
                        handle(data[inn.group(1)], doc)

    def revexp(row, doc):
        if m := re.search(r'СумДоход="([\d.]+)" СумРасход="([\d.]+)"', doc):
            row.update(revenue=float(m.group(1)), expenses=float(m.group(2)))

    def paytax(row, doc):
        row["taxes_paid"] = sum(float(x) for x in re.findall(r'СумУплНал="([\d.]+)"', doc))

    def debtam(row, doc):
        row["tax_debt"] = sum(float(x) for x in re.findall(r'ОбщСумНедоим="([\d.]+)"', doc))

    def sshr(row, doc):
        if m := re.search(r'КолРаб="(\d+)"', doc):
            row["headcount"] = int(m.group(1))

    for name, handle in (
        ("revexp.zip", revexp),
        ("paytax.zip", paytax),
        ("debtam.zip", debtam),
        ("sshr.zip", sshr),
    ):
        if (directory / name).exists():
            scan(name, handle)
    return data


def build(path: Path, fns_dir: Path | None) -> None:
    with pipeline.connect() as conn:
        suppliers = conn.execute(SUPPLIERS_SQL).fetchall()
    outside = [inn for inn, in_registry in suppliers if not in_registry and len(inn) == 10]
    print(f"    suppliers: {len(suppliers)}, companies outside the SME registry: {len(outside)}")
    rows: dict[str, dict] = defaultdict(dict)
    with ThreadPoolExecutor(4) as pool:
        for inn, found in zip(outside, pool.map(statements, outside), strict=True):
            rows[inn].update({k: v for k, v in found.items() if v is not None}, source="fns")
        for inn, found in zip(outside, pool.map(egrul, outside), strict=True):
            rows[inn].update({k: v for k, v in found.items() if v is not None}, source="egrul")
    if fns_dir:
        legal = {inn for inn, _ in suppliers if len(inn) == 10}
        for inn, found in fns_open_data(fns_dir, legal).items():
            rows[inn].update(found)  # the open data revenue (income) wins over the statements
            rows[inn].setdefault("source", "fns")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, FIELDS, delimiter=";")
        writer.writeheader()
        for inn in sorted(rows):
            writer.writerow({"inn": inn, **rows[inn]})
    print(f"    saved {len(rows)} organizations to {path}")


def load(path: Path) -> None:
    with pipeline.connect() as conn:
        pipeline.run_sql_file(conn, "organizations_schema.sql")
        with path.open(encoding="utf-8", newline="") as f, conn.cursor() as cur:
            with cur.copy("COPY organizations FROM STDIN") as copy:
                for r in csv.DictReader(f, delimiter=";"):
                    copy.write_row([r.get(k) or None for k in FIELDS])
        count = conn.execute("SELECT count(*) FROM organizations").fetchone()[0]
        conn.commit()
    print(f"    organizations: {count}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=RESOURCE)
    parser.add_argument("--build", action="store_true", help="collect the data again first")
    parser.add_argument("--fns-dir", type=Path, help="directory with the FNS open data zips")
    args = parser.parse_args()
    if args.build:
        with pipeline.timed("[09] Collecting open FNS data"):
            build(args.file, args.fns_dir)
    with pipeline.timed("[09] Loading organizations"):
        load(args.file)


if __name__ == "__main__":
    main()
