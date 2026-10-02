"""CSV upload validation, atomic failure, and complete recommendation responses."""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.ml.candidates import FEATURES
from app.ml.explainer import Facts
from app.schemas.lot import LotCard
from app.schemas.supplier import SearchFilters, SearchResponse
from app.services.csv_batch_service import MAX_FILE_BYTES, csv_batch_service, parse_uploads
from app.services.engine import Engine
from app.services.enrichment_service import enrichment_service
from app.services.search_service import search_service

NOTICES = (
    "publish_date;procedure_id;lot_id;start_price;reqnum;procedure_name;subject;is_smp;"
    "customer_inn;customer_kpp;is_eshop_or_aisgz\n"
    "2026-02-20;10;6029457;1000.50;001;Поставка бумаги;Бумага А4;false;7805045350;;АИС ГЗ\n"
)
ITEMS = "lot_id;product_name;okpd2_code\n6029457;Бумага А4;17.12.14.110\n"


def merged_notice_header(notices):
    header, rows = notices.split("\n", 1)
    fields = header.split(";")
    fields[4:6] = ["reqnum;procedure_name"]
    return ";".join(f'"{field}"' for field in fields) + "\n" + rows


@pytest.mark.parametrize("reqnum", ["001", ""])
def test_merged_notice_header_preserves_separate_row_fields(reqnum):
    notices = merged_notice_header(NOTICES.replace(";001;", f";{reqnum};"))
    notices = notices.replace(";Бумага А4;", ';"Бумага А4; белая";')
    lots, count = parse_uploads(notices.encode("utf-8-sig"), ITEMS.encode("utf-8-sig"))
    lot = lots[6029457]["lot"]
    assert count == 1
    assert lots[6029457]["procedure_name"] == "Поставка бумаги"
    assert lot.subject == "Бумага А4; белая"
    assert lot.is_smp is False
    assert lot.customer_inn == "7805045350"
    assert lot.channel == "АИС ГЗ"
    assert lot.items == ["Бумага А4"]


def test_real_test_files_are_joined_without_database_lookup():
    data = Path(__file__).resolve().parents[2] / "data" / "Тестовые данные"
    if not data.exists():
        pytest.skip("Local demo CSVs are not included in the repository")
    notices = next(data.glob("*извещения*.csv"))
    items = next(data.glob("*потоварка*.csv"))
    lots, count = parse_uploads(notices.read_bytes(), items.read_bytes())
    assert len(lots) == 38
    assert count == 670
    assert sum(len(entry["lot"].items) for entry in lots.values()) == 670
    assert lots[5968880]["lot"].start_price == 105188.82
    assert lots[5968880]["lot"].okpd2_codes == ["32.50.50.190"]


def test_bom_cp1251_and_quoted_multiline_products():
    items = 'lot_id,product_name,okpd2_code\n6029457,"Бумага, А4\nбелая",17.12.14.110\n'
    lots, count = parse_uploads(NOTICES.encode("utf-8-sig"), items.encode("cp1251"))
    assert count == 1
    assert lots[6029457]["lot"].items == ["Бумага, А4\nбелая"]


@pytest.mark.parametrize(
    "notices,items,message",
    [
        ("", ITEMS, "файл пуст"),
        (NOTICES.replace("subject;", "wrong;"), ITEMS, "отсутствуют столбцы"),
        (NOTICES + NOTICES.splitlines()[1] + "\n", ITEMS, "повторяется"),
        (NOTICES.replace("1000.50", "nan"), ITEMS, "конечным"),
        (NOTICES.replace("1000.50", "-1"), ITEMS, "неотрицательным"),
        (NOTICES.replace("2026-02-20", "2026-02-30"), ITEMS, "ГГГГ-ММ-ДД"),
        (NOTICES.replace("false", "maybe"), ITEMS, "is_smp"),
        (NOTICES, ITEMS.replace("6029457", "99"), "отсутствует в извещениях"),
        (NOTICES, ITEMS.replace("17.12.14.110", "не код"), "okpd2_code"),
        (NOTICES, ITEMS.replace("Бумага А4", ""), "product_name"),
        (NOTICES, ITEMS + "6029457;Тонер;17.12;лишнее\n", "число полей"),
        (NOTICES, ITEMS + '6029457;"незакрытая строка;17.12\n', "структура CSV"),
        (
            merged_notice_header(NOTICES).replace(
                ";001;Поставка бумаги;", ';"001;Поставка бумаги";'
            ),
            ITEMS,
            "число полей",
        ),
        (
            merged_notice_header(NOTICES) + NOTICES.splitlines()[1] + ";лишнее\n",
            ITEMS,
            "число полей",
        ),
        (
            merged_notice_header(NOTICES).replace('"subject"', '"reqnum"'),
            ITEMS,
            "названия столбцов повторяются",
        ),
    ],
)
def test_invalid_csv_rejects_entire_run_before_search(monkeypatch, notices, items, message):
    def unexpected(*args, **kwargs):
        pytest.fail("Matching must not start before all rows are validated")

    monkeypatch.setattr(search_service, "search", unexpected)
    with pytest.raises(HTTPException) as error:
        csv_batch_service.run(None, notices.encode(), items.encode())
    assert error.value.status_code == 422
    assert message in error.value.detail


def test_missing_product_positions_rejects_run():
    extra = NOTICES.splitlines()[1].replace("6029457", "123")
    with pytest.raises(HTTPException, match="нет товарных позиций"):
        parse_uploads((NOTICES + extra + "\n").encode(), ITEMS.encode())


def test_oversized_csv():
    with pytest.raises(HTTPException) as error:
        parse_uploads(b"a" * (MAX_FILE_BYTES + 1), ITEMS.encode())
    assert error.value.status_code == 413


@pytest.mark.parametrize("merged_header", [False, True])
def test_upload_endpoint_uses_raw_fields_and_returns_complete_result(monkeypatch, merged_header):
    requests = []

    def search(conn, request, *, automatic):
        requests.append(request)
        assert automatic is True
        assert request.lot_id is None
        card = LotCard(
            **request.lot.model_dump(),
            lot_id=None,
            publish_date=None,
            procedure_name=None,
            actual_winners=[],
        )
        return SearchResponse(lot=card, items=[], new_suppliers=[], total_candidates=0, timing_ms=1)

    monkeypatch.setattr(search_service, "search", search)
    app.dependency_overrides[get_db] = lambda: None
    try:
        client = TestClient(app)
        notices = merged_notice_header(NOTICES) if merged_header else NOTICES
        response = client.post(
            "/api/v1/batch/csv",
            files={
                "notices": ("notice.csv", notices.encode("utf-8-sig"), "text/csv"),
                "items": ("items.csv", ITEMS.encode(), "text/csv"),
            },
        )
        assert response.status_code == 200
        result = response.json()
        assert result["total_lots"] == 1
        assert result["total_items"] == 1
        assert result["lots"][0]["lot"]["lot_id"] == 6029457
        assert result["lots"][0]["lot"]["publish_date"] == "2026-02-20"
        assert result["lots"][0]["lot"]["procedure_name"] == "Поставка бумаги"
        assert result["supplier_cards"] == {}
        assert requests[0].lot.items == ["Бумага А4"]
        assert (
            client.post(
                "/api/v1/batch/csv",
                files={
                    "notices": ("notice.csv", NOTICES.encode(), "text/csv"),
                },
            ).status_code
            == 422
        )
    finally:
        app.dependency_overrides.clear()


def make_engine(scores):
    engine = object.__new__(Engine)
    count = len(scores)
    history = SimpleNamespace(
        inns=np.array([f"780000000{i}" for i in range(count)]),
        stats={},
        retrieve=lambda query: SimpleNamespace(candidates=np.arange(count)),
        features=lambda query, retrieval: np.zeros((count, len(FEATURES))),
    )
    engine.today = 1
    engine.snapshot = lambda cutoff: SimpleNamespace(history=history)
    engine.model = SimpleNamespace(predict=lambda features: np.array(scores))
    engine._passes = lambda *args: True
    engine._shap = lambda features: np.zeros((len(features), len(FEATURES)))
    engine._evidence = lambda *args: {}
    engine._customer_history = lambda *args: {}
    engine._facts = lambda *args: Facts()
    engine._new_suppliers = lambda *args: []
    return engine


@pytest.mark.parametrize("scores,expected", [([10, 9, 8, 2, 0], 3), ([10, 2, 1, 0], 1), ([], 0)])
def test_automatic_selection_varies_with_relevance(scores, expected):
    engine = make_engine(scores)
    card = LotCard(
        subject="Бумага",
        items=[],
        okpd2_codes=[],
        start_price=1000,
        customer_inn=None,
        channel=None,
        is_smp=False,
        lot_id=None,
        publish_date=None,
        procedure_name=None,
        actual_winners=[],
    )
    conn = SimpleNamespace(execute=lambda *args: SimpleNamespace(fetchall=lambda: []))
    filters = SearchFilters(
        roles=[], only_spb_lo=False, only_smp=False, min_win_rate=0, only_reliable=False
    )
    result = engine.search(conn, card, SimpleNamespace(day=1), [], filters, 100, 50, automatic=True)
    assert len(result.items) == expected
    # The existing single-lot flow still uses the caller's limit.
    legacy = engine.search(conn, card, SimpleNamespace(day=1), [], filters, 2, 0)
    assert len(legacy.items) == min(2, len(scores))


def test_supplier_details_are_included_once_for_repeated_companies(monkeypatch):
    from app.schemas.supplier import NewSupplier

    supplier = NewSupplier(
        inn="7800000000",
        name="Компания",
        role="SUPPLIER",
        role_display="Поставщик",
        okved_main="38.22",
        okved_name=None,
        region_code="78",
        msp_category=1,
        headcount=None,
        profile_fit=None,
        reason="ОКВЭД 38.22 + лицензия на отходы",
        score=1,
        base_score=1,
        reliability_factor=1,
        warnings=[],
    )
    calls = []

    def search(conn, request, **kwargs):
        card = LotCard(
            **request.lot.model_dump(),
            lot_id=None,
            publish_date=None,
            procedure_name=None,
            actual_winners=[],
        )
        return SearchResponse(
            lot=card, items=[], new_suppliers=[supplier], total_candidates=0, timing_ms=0
        )

    def enrich(conn, inn):
        calls.append(inn)
        raise HTTPException(404, "Нет компании")

    monkeypatch.setattr(search_service, "search", search)
    monkeypatch.setattr(enrichment_service, "supplier_card", enrich)
    notices = NOTICES + NOTICES.splitlines()[1].replace("6029457", "123") + "\n"
    items = ITEMS + ITEMS.splitlines()[1].replace("6029457", "123") + "\n"
    result = csv_batch_service.run(None, notices.encode(), items.encode())
    assert calls == [supplier.inn]
    assert supplier.inn in result.supplier_cards
    assert result.total_recommendations == 2
    assert result.lots[0].new_suppliers[0].reason == supplier.reason
