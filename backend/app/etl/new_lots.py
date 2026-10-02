"""Lots to recommend suppliers for, read from a notices CSV and an items (TRU) CSV in the format
of the training data. Values are cleaned the way clean.sql cleans them."""

import csv
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from app.etl.sources import inspect_file

TRUE = {"true", "t", "1", "yes", "y", "да"}


@dataclass
class InputLot:
    lot_id: int
    subject: str
    publish_date: date | None
    procedure_name: str | None
    start_price: float | None
    customer_inn: str | None
    channel: str | None
    is_smp: bool
    items: list[str] = field(default_factory=list)
    okpd2_codes: list[str] = field(default_factory=list)


def _text(value: str | None) -> str | None:
    return (value or "").strip() or None


def _bigint(value: str | None) -> int | None:
    value = (value or "").strip()
    return int(value) if re.fullmatch(r"\d{1,18}", value) else None


def _money(value: str | None) -> float | None:
    value = re.sub(r"\s", "", value or "").replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return None


def _date(value: str | None) -> date | None:
    value = (value or "").strip()
    return date.fromisoformat(value[:10]) if re.match(r"\d{4}-\d{2}-\d{2}", value) else None


def _inn(value: str | None) -> str | None:
    value = (value or "").strip()
    return value if re.fullmatch(r"\d{10}|\d{12}", value) else None


def _okpd2(value: str | None) -> str | None:
    value = (value or "").strip()
    return value if re.fullmatch(r"\d{2}(\.\d{1,3})*", value) else None


def rows(path: Path, kind: str) -> Iterator[dict[str, str]]:
    """Rows of a CSV of the given kind (notices, items, bids) as dicts by lowercase column."""
    raw = inspect_file(path)
    if raw is None or raw.kind != kind:
        raise ValueError(f"{path}: not a {kind} CSV (columns are detected as in 01_init_db)")
    with path.open(encoding=raw.encoding, newline="") as f:
        reader = csv.reader(f, delimiter=raw.delimiter)
        header = [c.strip().lstrip("﻿").strip().lower() for c in next(reader)]
        for row in reader:
            yield dict(zip(header, row, strict=False))


def read_lots(notices: Path, items: Path) -> list[InputLot]:
    lots: dict[int, InputLot] = {}
    for r in rows(notices, "notices"):
        lot_id = _bigint(r.get("lot_id"))
        if lot_id is None:
            continue
        procedure = _text(r.get("procedure_name"))
        lots[lot_id] = InputLot(
            lot_id=lot_id,
            subject=_text(r.get("subject")) or procedure or "",
            publish_date=_date(r.get("publish_date")),
            procedure_name=procedure,
            start_price=_money(r.get("start_price")),
            customer_inn=_inn(r.get("customer_inn")),
            channel=_text(r.get("is_eshop_or_aisgz")),
            is_smp=(r.get("is_smp") or "").strip().lower() in TRUE,
        )
    for r in rows(items, "items"):
        lot = lots.get(_bigint(r.get("lot_id")))
        if lot is None:
            continue
        if name := _text(r.get("product_name")):
            lot.items.append(name)
        if (code := _okpd2(r.get("okpd2_code"))) and code not in lot.okpd2_codes:
            lot.okpd2_codes.append(code)
    return list(lots.values())


def read_winners(bids: Path) -> dict[int, set[str]]:
    """Winner INNs per lot from a suppliers CSV, to check the recommendations."""
    winners: dict[int, set[str]] = {}
    for r in rows(bids, "bids"):
        lot_id, inn = _bigint(r.get("lot_id")), _inn(r.get("supplier_inn"))
        if lot_id is not None and inn and (r.get("is_winner") or "").strip().lower() in TRUE:
            winners.setdefault(lot_id, set()).add(inn)
    return winners
