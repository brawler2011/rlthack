"""Поиск исходных CSV и определение их формата: тип файла, кодировка, разделитель."""

import codecs
import csv
from dataclasses import dataclass
from pathlib import Path

# Тип файла узнаём по ключевой колонке, а не по имени: так не важно, как назван файл.
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
    encoding: str  # имя кодека Python: utf-8 или cp1251

    @property
    def pg_encoding(self) -> str:
        return PG_ENCODINGS[self.encoding]


def detect_encoding(sample: bytes) -> str:
    """UTF-8, если начало файла декодируется без ошибок, иначе cp1251."""
    try:
        # final=False: обрезанный на границе выборки многобайтный символ не считается ошибкой
        codecs.getincrementaldecoder("utf-8")().decode(sample, final=False)
        return "utf-8"
    except UnicodeDecodeError:
        return "cp1251"


def inspect_file(path: Path) -> RawFile | None:
    """Определяет тип и формат CSV по заголовку. None, если это не один из наших файлов."""
    with path.open("rb") as f:
        sample = f.read(SAMPLE_SIZE)
    encoding = detect_encoding(sample)
    lines = sample.decode(encoding, errors="ignore").lstrip("﻿").splitlines()
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
                raise ValueError(f"{path.name}: похоже на «{kind}», но нет колонок {missing}")
            return RawFile(kind, path, columns, delimiter, encoding)
    return None


def detect_sources(raw_dir: Path) -> dict[str, list[RawFile]]:
    """Находит в папке (с подпапками) CSV извещений, ТРУ и поставщиков."""
    if not raw_dir.is_dir():
        raise FileNotFoundError(f"Нет папки с исходными данными: {raw_dir}")

    sources: dict[str, list[RawFile]] = {kind: [] for kind in KEY_COLUMNS}
    for path in sorted(p for p in raw_dir.rglob("*") if p.suffix.lower() == ".csv"):
        raw = inspect_file(path)
        if raw is not None:
            sources[raw.kind].append(raw)

    missing = [kind for kind, files in sources.items() if not files]
    if missing:
        raise FileNotFoundError(
            f"В {raw_dir} не найдены CSV для {missing}. "
            f"Файлы узнаются по колонкам: {', '.join(KEY_COLUMNS.values())}"
        )
    return sources
