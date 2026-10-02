"""Validate both uploaded CSVs completely before matching any procurement."""

import csv
import io
import math
import re
import time
from datetime import date

from fastapi import HTTPException

from app.schemas.csv_batch import CsvBatchResponse
from app.schemas.lot import NewLot
from app.schemas.supplier import SearchFilters, SearchRequest
from app.services.enrichment_service import enrichment_service
from app.services.search_service import search_service

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_LOTS = 100
MAX_ITEMS = 5000
NOTICE_COLUMNS = {
    "publish_date",
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
}
ITEM_COLUMNS = {"lot_id", "product_name", "okpd2_code"}
SELECTION_POLICY = (
    "Показаны поставщики с баллом не ниже 66% от лучшего в своей группе. "
    "Балл отражает относительное соответствие закупке, а не вероятность победы."
)


def invalid(label: str, line: int | None, message: str):
    location = f", строка {line}" if line is not None else ""
    raise HTTPException(422, f"{label}{location}: {message}. Весь запуск отклонён.")


def read_csv(content: bytes, label: str, columns: set[str], max_rows: int):
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, f"{label}: размер файла превышает 2 МБ.")
    if not content:
        invalid(label, None, "файл пуст")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("cp1251")
        except UnicodeDecodeError:
            invalid(label, None, "поддерживаются кодировки UTF-8 и Windows-1251")
    if "\x00" in text:
        invalid(label, None, "ожидается текстовый CSV")
    # Detect the separator from the header, not from variable-length product descriptions.
    header = text.splitlines()[0] if text.splitlines() else ""
    delimiter = ";" if header.count(";") > header.count(",") else ","
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
    try:
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)):
            invalid(label, 1, "названия столбцов повторяются")
        missing = columns - set(fields)
        if missing:
            invalid(label, 1, f"отсутствуют столбцы: {', '.join(sorted(missing))}")
        rows = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                invalid(label, reader.line_num, "число полей не совпадает с заголовком")
            rows.append((reader.line_num, {key: value.strip() for key, value in row.items()}))
            if len(rows) > max_rows:
                invalid(label, reader.line_num, f"допускается не более {max_rows} строк")
    except csv.Error:
        invalid(label, reader.line_num, "некорректная структура CSV")
    if not rows:
        invalid(label, None, "нет строк с данными")
    return rows


def positive_id(value: str, label: str, line: int, field: str = "lot_id") -> int:
    if len(value) > 18 or not re.fullmatch(r"[0-9]+", value) or int(value) <= 0:
        invalid(label, line, f"{field} должен быть положительным целым числом")
    return int(value)


def parse_uploads(notices: bytes, items: bytes):
    notice_rows = read_csv(notices, "Извещения", NOTICE_COLUMNS, MAX_LOTS)
    item_rows = read_csv(items, "Потоварка", ITEM_COLUMNS, MAX_ITEMS)
    lots = {}
    for line, row in notice_rows:
        lot_id = positive_id(row["lot_id"], "Извещения", line)
        positive_id(row["procedure_id"], "Извещения", line, "procedure_id")
        if lot_id in lots:
            invalid("Извещения", line, f"lot_id {lot_id} повторяется")
        try:
            published = date.fromisoformat(row["publish_date"])
        except ValueError:
            invalid("Извещения", line, "publish_date должен быть датой ГГГГ-ММ-ДД")
        try:
            price = float(row["start_price"].replace(",", "."))
        except ValueError:
            invalid("Извещения", line, "start_price должен быть числом")
        if not math.isfinite(price) or price < 0:
            invalid("Извещения", line, "start_price должен быть конечным неотрицательным числом")
        if len(row["subject"]) < 3:
            invalid("Извещения", line, "subject должен содержать не менее трёх символов")
        if row["is_smp"].lower() not in {"true", "false", "1", "0"}:
            invalid("Извещения", line, "is_smp должен быть true, false, 1 или 0")
        if row["customer_inn"] and not re.fullmatch(r"[0-9]{10}|[0-9]{12}", row["customer_inn"]):
            invalid("Извещения", line, "customer_inn должен содержать 10 или 12 цифр")
        lots[lot_id] = {
            "lot": NewLot(
                subject=row["subject"],
                items=[],
                okpd2_codes=[],
                start_price=price,
                customer_inn=row["customer_inn"] or None,
                channel=row["is_eshop_or_aisgz"] or None,
                is_smp=row["is_smp"].lower() in {"true", "1"},
            ),
            "publish_date": published,
            "procedure_name": row["procedure_name"] or None,
            "line": line,
        }
    for line, row in item_rows:
        lot_id = positive_id(row["lot_id"], "Потоварка", line)
        if lot_id not in lots:
            invalid("Потоварка", line, f"lot_id {lot_id} отсутствует в извещениях")
        if not row["product_name"]:
            invalid("Потоварка", line, "product_name не может быть пустым")
        code = row["okpd2_code"]
        if not re.fullmatch(r"[0-9]{2}(?:\.[0-9]{1,3}){0,3}", code):
            invalid("Потоварка", line, "некорректный okpd2_code")
        lot = lots[lot_id]["lot"]
        lot.items.append(row["product_name"])
        if code not in lot.okpd2_codes:
            lot.okpd2_codes.append(code)
    for lot_id, entry in lots.items():
        if not entry["lot"].items:
            invalid("Извещения", entry["line"], f"для lot_id {lot_id} нет товарных позиций")
    return lots, len(item_rows)


class CsvBatchService:
    def run(self, conn, notices: bytes, items: bytes) -> CsvBatchResponse:
        started = time.perf_counter()
        uploaded, total_items = parse_uploads(notices, items)
        results = []
        cards = {}
        filters = SearchFilters(
            roles=[], only_spb_lo=False, only_smp=False, min_win_rate=0, only_reliable=False
        )
        for lot_id, entry in uploaded.items():
            # Always match uploaded fields as a new query; never resolve the ID in the database.
            request = SearchRequest(
                lot_id=None, lot=entry["lot"], filters=filters, limit=100, new_limit=50
            )
            found = search_service.search(conn, request, automatic=True)
            found.lot.lot_id = lot_id
            found.lot.publish_date = entry["publish_date"]
            found.lot.procedure_name = entry["procedure_name"]
            results.append(found)
            for supplier in [*found.items, *found.new_suppliers]:
                if supplier.inn not in cards:
                    try:
                        cards[supplier.inn] = enrichment_service.supplier_card(conn, supplier.inn)
                    except HTTPException as error:
                        if error.status_code != 404:
                            raise
                        cards[supplier.inn] = None
        return CsvBatchResponse(
            lots=results,
            supplier_cards=cards,
            total_lots=len(results),
            total_items=total_items,
            total_recommendations=sum(len(r.items) + len(r.new_suppliers) for r in results),
            timing_ms=round((time.perf_counter() - started) * 1000, 1),
            selection_policy=SELECTION_POLICY,
        )


csv_batch_service = CsvBatchService()
