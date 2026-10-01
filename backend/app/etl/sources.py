"""Find the source CSVs and detect their format: file type, encoding, delimiter."""

import codecs
import csv
from dataclasses import dataclass
from pathlib import Path

# The file type is detected by a key column, not by name, so file names don't matter.
KEY_COLUMNS = {
    "notices": "procedure_id",
    "items": "product_name",
    "bids": "supplier_inn",
}

REQUIRED_COLUMNS = {
    "notices": (
        "procedure_id",
        "lot_id",
        "start_price",
        "reqnum",
        "procedure_name",
        "subject",
        "is_smp",
        "customer_inn",
        "customer_kpp",
        "is_eshop_or_aisgz",
    ),
    "items": ("lot_id", "product_name", "okpd2_code"),
    "bids": ("lot_id", "supplier_inn", "supplier_kpp", "is_winner"),
}

DELIMITERS = (";", ",", "\t", "|")
PG_ENCODINGS = {"utf-8": "UTF8", "cp1251": "WIN1251"}
SAMPLE_SIZE = 1 << 20


@dataclass(frozen=True)
class RawFile:
    kind: str
    path: Path
    columns: tuple[str, ...]
    delimiter: str
    encoding: str  # Python codec name: utf-8 or cp1251

    @property
    def pg_encoding(self) -> str:
        return PG_ENCODINGS[self.encoding]


def detect_encoding(sample: bytes) -> str:
    """UTF-8 if the start of the file decodes cleanly, cp1251 otherwise."""
    try:
        # final=False: a multibyte char cut at the sample boundary is not an error
        codecs.getincrementaldecoder("utf-8")().decode(sample, final=False)
        return "utf-8"
    except UnicodeDecodeError:
        return "cp1251"


def inspect_file(path: Path) -> RawFile | None:
    """Detect CSV type and format from its header. None if it is not one of our files."""
    with path.open("rb") as f:
        sample = f.read(SAMPLE_SIZE)
    encoding = detect_encoding(sample)
    lines = sample.decode(encoding, errors="ignore").lstrip("\ufeff").splitlines()
    if not lines:
        return None

    for delimiter in DELIMITERS:
        header = next(csv.reader([lines[0]], delimiter=delimiter))
        columns = tuple(c.strip().lower() for c in header)
        for kind, key in KEY_COLUMNS.items():
            if key not in columns:
                continue
            missing = [c for c in REQUIRED_COLUMNS[kind] if c not in columns]
            if missing:
                raise ValueError(f"{path.name}: looks like {kind!r} but lacks columns {missing}")
            return RawFile(kind, path, columns, delimiter, encoding)
    return None


def detect_sources(raw_dir: Path) -> dict[str, list[RawFile]]:
    """Find notice, TRU item and supplier CSVs in a directory (recursively)."""
    if not raw_dir.is_dir():
        raise FileNotFoundError(f"Source data directory not found: {raw_dir}")

    sources: dict[str, list[RawFile]] = {kind: [] for kind in KEY_COLUMNS}
    for path in sorted(p for p in raw_dir.rglob("*") if p.suffix.lower() == ".csv"):
        raw = inspect_file(path)
        if raw is not None:
            sources[raw.kind].append(raw)

    missing = [kind for kind, files in sources.items() if not files]
    if missing:
        raise FileNotFoundError(
            f"No CSVs for {missing} found in {raw_dir}. "
            f"Files are detected by columns: {', '.join(KEY_COLUMNS.values())}"
        )
    return sources
