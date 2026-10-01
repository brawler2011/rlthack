"""Companies from the FNS SME registry (open data): name, OKVED, category, declared products.

The dump is a zip of XML files, one <Документ> per company. Only companies from the given
regions or with the given INNs are parsed: a quick text check skips everything else.
"""

import re
import zipfile
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

RMSP_URL = "https://www.nalog.gov.ru/opendata/7707329152-rsmp/"

_DOC = re.compile(r"<Документ\b.*?</Документ>", re.S)
_INN = re.compile(r'ИНН(?:ЮЛ|ФЛ)="(\d+)"')
_REGION = re.compile(r'КодРегион="(\d+)"')
_ENCODING = re.compile(rb'encoding="([^"]+)"')


@dataclass
class Company:
    inn: str
    name: str
    is_individual: bool
    region: str | None
    category: int | None  # 1 micro, 2 small, 3 medium
    headcount: int | None
    msp_since: date | None
    okved_main: str | None
    okved_main_name: str | None
    okved_extra: list[str]
    products: list[str]  # declared product codes


def _date(value: str | None) -> date | None:
    return datetime.strptime(value, "%d.%m.%Y").date() if value else None


def _int(value: str | None) -> int | None:
    return int(value) if value and value.isdigit() else None


def parse_document(xml: str) -> Company | None:
    doc = ET.fromstring(xml)
    org, ip = doc.find("ОргВклМСП"), doc.find("ИПВклМСП")
    if org is not None:
        inn, name = org.get("ИННЮЛ"), org.get("НаимОргСокр") or org.get("НаимОрг")
    elif ip is not None:
        fio = ip.find("ФИОИП")
        parts = [fio.get(k) for k in ("Фамилия", "Имя", "Отчество")] if fio is not None else []
        inn, name = ip.get("ИННФЛ"), "ИП " + " ".join(p for p in parts if p)
    else:
        return None
    place = doc.find("СведМН")
    main = doc.find("СвОКВЭД/СвОКВЭДОсн")
    return Company(
        inn=inn,
        name=name,
        is_individual=ip is not None,
        region=place.get("КодРегион") if place is not None else None,
        category=_int(doc.get("КатСубМСП")),
        headcount=_int(doc.get("ССЧР")),
        msp_since=_date(doc.get("ДатаВклМСП")),
        okved_main=main.get("КодОКВЭД") if main is not None else None,
        okved_main_name=main.get("НаимОКВЭД") if main is not None else None,
        okved_extra=[e.get("КодОКВЭД") for e in doc.findall("СвОКВЭД/СвОКВЭДДоп")],
        products=[p.get("КодПрод") for p in doc.findall("СвПрод") if p.get("КодПрод")],
    )


def parse_xml(raw: bytes, regions: set[str], inns: set[str]) -> list[Company]:
    """Companies of one XML file that are in the regions or have one of the INNs."""
    match = _ENCODING.search(raw[:200])
    text = raw.decode(match.group(1).decode() if match else "utf-8")
    companies = []
    for block in _DOC.finditer(text):
        xml = block.group()
        region, inn = _REGION.search(xml), _INN.search(xml)
        if (region and region.group(1) in regions) or (inn and inn.group(1) in inns):
            company = parse_document(xml)
            if company is not None:
                companies.append(company)
    return companies


_filters: tuple[set[str], set[str]] = (set(), set())


def _init_worker(regions: set[str], inns: set[str]) -> None:
    global _filters
    _filters = (regions, inns)


def _parse_member(args: tuple[Path, str]) -> list[Company]:
    path, member = args
    with zipfile.ZipFile(path) as z:
        return parse_xml(z.read(member), *_filters)


def read_dump(path: Path, regions: set[str], inns: set[str], workers: int = 4) -> list[Company]:
    """All matching companies from the registry zip, parsed in parallel processes."""
    with zipfile.ZipFile(path) as z:
        members = [m for m in z.namelist() if m.lower().endswith(".xml")]
    companies: list[Company] = []
    with ProcessPoolExecutor(workers, initializer=_init_worker, initargs=(regions, inns)) as pool:
        for chunk in pool.map(_parse_member, [(path, m) for m in members], chunksize=16):
            companies.extend(chunk)
    return companies


def latest_dump_url(page_url: str = RMSP_URL) -> str:
    """Link to the newest registry dump listed on the FNS open data page."""
    from urllib.request import urlopen

    html = urlopen(page_url, timeout=60).read().decode("utf-8", errors="ignore")
    links = set(
        re.findall(r"https://file\.nalog\.ru/opendata/[^\"]+/data-(\d{8})-[^\"]+\.zip", html)
    )
    if not links:
        raise RuntimeError(f"No registry dumps found on {page_url}")
    newest = max(links, key=lambda d: (d[4:], d[2:4], d[:2]))  # ddmmyyyy
    return re.search(
        rf"https://file\.nalog\.ru/opendata/[^\"]+/data-{newest}-[^\"]+\.zip", html
    ).group()


def download(url: str, path: Path, workers: int = 12, chunk: int = 32 << 20) -> None:
    """Download in parallel ranges, resuming a partial file.

    The FNS server limits each connection to a few hundred KB/s, so one stream takes hours.
    """
    from concurrent.futures import ThreadPoolExecutor
    from urllib.request import Request, urlopen

    size = int(urlopen(Request(url, method="HEAD"), timeout=60).headers["Content-Length"])
    path.parent.mkdir(parents=True, exist_ok=True)
    done = path.stat().st_size if path.exists() else 0
    parts = path.with_name(path.name + ".parts")
    parts.mkdir(exist_ok=True)
    ranges = [(a, min(a + chunk, size) - 1) for a in range(done, size, chunk)]

    def fetch(bounds: tuple[int, int]) -> Path:
        a, b = bounds
        part = parts / f"{a:012d}"
        for _ in range(10):
            if part.exists() and part.stat().st_size == b - a + 1:
                return part
            try:
                request = Request(url, headers={"Range": f"bytes={a}-{b}"})
                with urlopen(request, timeout=60) as response:
                    part.write_bytes(response.read())
            except OSError:
                continue
        raise RuntimeError(f"Range {a}-{b} of {url} failed")

    with ThreadPoolExecutor(workers) as pool:
        finished = list(pool.map(fetch, ranges))
    with path.open("ab") as f:
        for part in finished:
            f.write(part.read_bytes())
            part.unlink()
    parts.rmdir()
    if path.stat().st_size != size:
        raise RuntimeError(f"{path} has {path.stat().st_size} bytes, expected {size}")
