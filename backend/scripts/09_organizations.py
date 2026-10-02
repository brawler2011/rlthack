"""Script 09: Open FNS data about suppliers: names, OKVED, status, revenue, taxes, tax debt.

Loads resources/organizations.csv into the organizations table. The API shows names and roles
of suppliers outside the SME registry (large companies, state institutions) and reliability
warnings next to the recommendations.

--build rebuilds the file (needs the internet, about an hour):
  * names and registration dates from the public EGRUL search (egrul.nalog.ru) and OKVED, status
    and revenue from the accounting statements registry (bo.nalog.gov.ru), for the suppliers
    outside the SME registry, a few requests a second;
  * with --fns-dir: revenue and expenses (revexp), taxes paid (paytax), tax debt (debtam) and
    headcount (sshr2019) of every supplier and every SME registry legal entity, from the zips
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
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.etl import pipeline, rmsp  # noqa: E402

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
    "tax_fines",
    "revenue_as_of",
    "taxes_paid_as_of",
    "tax_debt_as_of",
    "headcount_as_of",
    "tax_fines_as_of",
    "refreshed_at",
)
HEADERS = {"User-Agent": "Mozilla/5.0"}
FNS_DATASETS = {
    "debtam": "debtam",
    "taxoffence": "taxoffence",
    "revexp": "revexp",
    "paytax": "paytax",
    "sshr": "sshr2019",
}
SUPPLIERS_SQL = """
SELECT q.inn, c.inn IS NOT NULL
FROM (SELECT supplier_inn AS inn FROM bids UNION SELECT inn FROM companies) q
LEFT JOIN companies c ON c.inn = q.inn
"""


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


def download_fns(directory: Path, datasets: list[str] | None = None) -> None:
    """Resolve current archive URLs from official dataset pages and keep local copies."""
    directory.mkdir(parents=True, exist_ok=True)
    for filename, dataset in FNS_DATASETS.items():
        if datasets is not None and filename not in datasets:
            continue
        page = f"https://www.nalog.gov.ru/opendata/7707329152-{dataset}/"
        request = urllib.request.Request(page, headers=HEADERS)
        with urllib.request.urlopen(request, timeout=60) as response:
            html = response.read().decode("utf-8")
        links = re.findall(
            rf'https://(?:file|data)\.nalog\.ru/opendata/7707329152-{dataset}/data-(\d{{8}})-[^"<>\s]+\.zip',
            html,
        )
        if not links:
            raise RuntimeError(f"No FNS archive found on {page}")
        newest = max(links)  # FNS financial datasets use YYYYMMDD release dates.
        url = re.search(
            rf'https://(?:file|data)\.nalog\.ru/opendata/7707329152-{dataset}/data-{newest}-[^"<>\s]+\.zip',
            html,
        ).group()
        # A dated file cannot be mistaken for a newer snapshot on a subsequent run.
        dated = directory / url.rsplit("/", 1)[1].replace("data-", f"{filename}-", 1)
        if not dated.exists() or not zipfile.is_zipfile(dated):
            print(f"    downloading {url}", flush=True)
            rmsp.download(url, dated, workers=16, chunk=8 << 20)
        target = directory / f"{filename}.zip"
        target.unlink(missing_ok=True)
        target.symlink_to(dated.name)


def fns_open_data(directory: Path, inns: set[str]) -> dict[str, dict]:
    """Stream XML archives once for the entire pool, including SMEs without bids."""
    data: dict[str, dict] = defaultdict(dict)

    def scan(name, handle, date_field):
        with zipfile.ZipFile(directory / name) as z:
            for member in z.namelist():
                if not member.lower().endswith(".xml"):
                    continue
                with z.open(member) as stream:
                    events = ET.iterparse(stream, events=("start", "end"))
                    _, root = next(events)
                    for event, doc in events:
                        if event != "end" or doc.tag != "Документ":
                            continue
                        org = doc.find("СведНП")
                        inn = org.get("ИННЮЛ") if org is not None else None
                        if inn in inns:
                            row = data[inn]
                            as_of = doc.get("ДатаСост")
                            parsed_date = (
                                datetime.strptime(as_of, "%d.%m.%Y").date().isoformat()
                                if as_of
                                else None
                            )
                            # Archives may contain multiple reporting dates for one INN.
                            if not row.get(date_field) or (
                                parsed_date and parsed_date >= row[date_field]
                            ):
                                handle(row, doc)
                                if parsed_date:
                                    row[date_field] = parsed_date
                        root.clear()

    def revexp(row, doc):
        for values in doc.iter():
            for field, attribute in (("revenue", "СумДоход"), ("expenses", "СумРасход")):
                if values.get(attribute) is not None:
                    row[field] = float(values.get(attribute))

    def paytax(row, doc):
        row["taxes_paid"] = float(
            sum(
                (Decimal(e.get("СумУплНал")) for e in doc.iter() if e.get("СумУплНал") is not None),
                Decimal(0),
            )
        )

    def debtam(row, doc):
        row["tax_debt"] = float(
            sum(
                (
                    Decimal(e.get("ОбщСумНедоим"))
                    for e in doc.iter()
                    if e.get("ОбщСумНедоим") is not None
                ),
                Decimal(0),
            )
        )

    def sshr(row, doc):
        for element in doc.iter():
            if element.get("КолРаб") is not None:
                row["headcount"] = int(element.get("КолРаб"))

    def taxoffence(row, doc):
        row["tax_fines"] = float(
            sum(
                (Decimal(e.get("СумШтраф")) for e in doc.iter() if e.get("СумШтраф") is not None),
                Decimal(0),
            )
        )

    for name, handle, date_field in (
        ("revexp.zip", revexp, "revenue_as_of"),
        ("paytax.zip", paytax, "taxes_paid_as_of"),
        ("debtam.zip", debtam, "tax_debt_as_of"),
        ("sshr.zip", sshr, "headcount_as_of"),
        ("taxoffence.zip", taxoffence, "tax_fines_as_of"),
    ):
        if (directory / name).exists():
            print(f"    parsing {name}", flush=True)
            scan(name, handle, date_field)
    return data


def build(
    path: Path,
    fns_dir: Path | None,
    registry_details: bool = False,
    bulk_only: bool = False,
    registry_dump: Path | None = None,
    resource_only: bool = False,
) -> None:
    if resource_only:
        with path.open(encoding="utf-8", newline="") as f:
            suppliers = [(row["inn"], True) for row in csv.DictReader(f, delimiter=";")]
    elif registry_dump is None:
        with pipeline.connect() as conn:
            suppliers = conn.execute(SUPPLIERS_SQL).fetchall()
    else:
        # Build a distributable resource without initializing a local PostgreSQL database.
        from app.etl.sources import detect_sources

        bidder_inns = set()
        for raw in detect_sources(settings.raw_data_dir).get("bids", []):
            with raw.path.open(encoding=raw.encoding, newline="") as f:
                for row in csv.DictReader(f, delimiter=raw.delimiter):
                    inn = (row.get("supplier_inn") or "").strip()
                    if inn.isdigit() and len(inn) in (10, 12):
                        bidder_inns.add(inn)
        registry_inns = {c.inn for c in rmsp.read_dump(registry_dump, {"78", "47"}, bidder_inns)}
        suppliers = [(inn, inn in registry_inns) for inn in sorted(bidder_inns | registry_inns)]
    outside = [inn for inn, in_registry in suppliers if not in_registry and len(inn) == 10]
    legal = {inn for inn, _ in suppliers if len(inn) == 10}
    print(
        f"    companies: {len(suppliers)}, legal entities: {len(legal)}, "
        f"outside MSP: {len(outside)}"
    )
    rows: dict[str, dict] = defaultdict(dict)
    refreshed_fields = set()
    for filename, fields in (
        ("revexp", ("revenue", "expenses", "revenue_as_of")),
        ("paytax", ("taxes_paid", "taxes_paid_as_of")),
        ("debtam", ("tax_debt", "tax_debt_as_of")),
        ("sshr", ("headcount", "headcount_as_of")),
        ("taxoffence", ("tax_fines", "tax_fines_as_of")),
    ):
        if fns_dir and (fns_dir / f"{filename}.zip").exists():
            refreshed_fields.update(fields)
    # Keep metadata, but do not retain stale risks missing from a refreshed dataset.
    if path.exists():
        with path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f, delimiter=";"):
                if row["inn"] in legal:
                    rows[row["inn"]].update(
                        {
                            k: v
                            for k, v in row.items()
                            if k != "inn" and v != "" and k not in refreshed_fields
                        }
                    )
    details = [] if bulk_only else sorted(legal) if registry_details else outside
    with ThreadPoolExecutor(4) as pool:
        for inn, found in zip(details, pool.map(statements, details), strict=True):
            rows[inn].update({k: v for k, v in found.items() if v is not None}, source="fns")
        for inn, found in zip(details, pool.map(egrul, details), strict=True):
            rows[inn].update({k: v for k, v in found.items() if v is not None}, source="egrul")
    if fns_dir:
        for inn, found in fns_open_data(fns_dir, legal).items():
            rows[inn].update(found, refreshed_at=date.today().isoformat())
            rows[inn].setdefault("source", "fns")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".csv.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, FIELDS, delimiter=";", lineterminator="\n")
        writer.writeheader()
        for inn in sorted(rows):
            writer.writerow({"inn": inn, **rows[inn]})
    temporary.replace(path)
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
    parser.add_argument(
        "--resource-only",
        action="store_true",
        help="refresh every company already in the resource without querying PostgreSQL",
    )
    parser.add_argument(
        "--registry-dump",
        type=Path,
        help="build from the SME dump and procurement CSVs instead of PostgreSQL",
    )
    parser.add_argument(
        "--no-load", action="store_true", help="build the resource without loading PostgreSQL"
    )
    parser.add_argument(
        "--download-fns", action="store_true", help="download current FNS archives before building"
    )
    parser.add_argument(
        "--bulk-only", action="store_true", help="refresh archives without individual web requests"
    )
    parser.add_argument(
        "--registry-details",
        action="store_true",
        help="also query EGRUL and statements for SME legal entities (many individual requests)",
    )
    args = parser.parse_args()
    if args.download_fns:
        args.build = True
        args.fns_dir = args.fns_dir or settings.data_dir / "external" / "fns"
        download_fns(args.fns_dir)
    if args.bulk_only and not (args.build and args.fns_dir):
        parser.error("--bulk-only requires --build and --fns-dir (or --download-fns)")
    if args.bulk_only and args.registry_details:
        parser.error("--bulk-only cannot be combined with --registry-details")
    if args.resource_only and not (args.build and args.bulk_only):
        parser.error("--resource-only requires --build and --bulk-only")
    if args.build:
        with pipeline.timed("[09] Collecting open FNS data"):
            build(
                args.file,
                args.fns_dir,
                args.registry_details,
                args.bulk_only,
                args.registry_dump,
                args.resource_only,
            )
    if not args.no_load:
        with pipeline.timed("[09] Loading organizations"):
            load(args.file)


if __name__ == "__main__":
    main()
