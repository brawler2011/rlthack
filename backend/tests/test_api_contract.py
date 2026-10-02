"""The strict generated contract stays aligned with the working matching API."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi.exceptions import ResponseValidationError
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.schemas.lot import LotCard, NewLot
from app.schemas.supplier import SearchFilters, SearchRequest, SearchResponse, SupplierCard
from app.services.engine import Engine, engine_state
from app.services.enrichment_service import enrichment_service
from app.services.search_service import search_service

LOT = {
    "subject": "Ноутбуки",
    "items": [],
    "okpd2_codes": ["26.20"],
    "start_price": 100000,
    "is_smp": False,
    "customer_inn": None,
    "channel": None,
}
FILTERS = {"roles": [], "only_spb_lo": False, "only_smp": False, "min_win_rate": 0}
REQUEST = {"lot_id": None, "lot": LOT, "filters": FILTERS, "limit": 20, "new_limit": 10}


@pytest.fixture
def client(monkeypatch):
    app.dependency_overrides[get_db] = lambda: None
    card = LotCard(**LOT, lot_id=None, publish_date=None, procedure_name=None, actual_winners=[])
    result = SearchResponse(lot=card, items=[], new_suppliers=[], total_candidates=0, timing_ms=0)
    monkeypatch.setattr(search_service, "search", lambda conn, request: result)
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize("field", SearchRequest.model_fields)
def test_missing_request_key_is_rejected(client, field):
    body = deepcopy(REQUEST)
    del body[field]
    response = client.post("/api/v1/suppliers/search", json=body)
    assert response.status_code == 422
    assert any(issue["type"] == "missing" for issue in response.json()["detail"])


@pytest.mark.parametrize("field", NewLot.model_fields)
def test_missing_lot_key_is_rejected(client, field):
    body = deepcopy(REQUEST)
    del body["lot"][field]
    assert client.post("/api/v1/suppliers/search", json=body).status_code == 422


@pytest.mark.parametrize("field", SearchFilters.model_fields)
def test_missing_filter_key_is_rejected(client, field):
    body = deepcopy(REQUEST)
    del body["filters"][field]
    assert client.post("/api/v1/suppliers/search", json=body).status_code == 422


@pytest.mark.parametrize("target", ["root", "lot", "filters"])
def test_unknown_keys_are_rejected(client, target):
    body = deepcopy(REQUEST)
    (body if target == "root" else body[target])["unexpected"] = 1
    response = client.post("/api/v1/suppliers/search", json=body)
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "extra_forbidden"


@pytest.mark.parametrize(
    "field,value",
    [
        ("roles", None),
        ("roles", ["OTHER"]),
        ("min_win_rate", None),
        ("min_win_rate", -0.1),
        ("min_win_rate", 1.1),
    ],
)
def test_invalid_filters_are_rejected(client, field, value):
    body = deepcopy(REQUEST)
    body["filters"][field] = value
    assert client.post("/api/v1/suppliers/search", json=body).status_code == 422


@pytest.mark.parametrize(
    "field,value",
    [("limit", 0), ("limit", 101), ("new_limit", -1), ("new_limit", 51), ("lot_id", 0)],
)
def test_invalid_request_ranges(client, field, value):
    body = deepcopy(REQUEST)
    body[field] = value
    assert client.post("/api/v1/suppliers/search", json=body).status_code == 422


def test_numeric_conversion_and_explicit_nulls(client):
    body = deepcopy(REQUEST)
    body["limit"] = "20"
    body["lot"]["start_price"] = "100000"
    response = client.post("/api/v1/suppliers/search", json=body)
    assert response.status_code == 200
    assert set(response.json()["lot"]) == set(LotCard.model_fields)
    assert response.json()["lot"]["lot_id"] is None


@pytest.mark.parametrize("price,status", [(0, 200), (None, 200), (-1, 422)])
def test_price_boundary(client, price, status):
    body = deepcopy(REQUEST)
    body["lot"]["start_price"] = price
    assert client.post("/api/v1/suppliers/search", json=body).status_code == status


def test_exactly_one_lot(client):
    body = deepcopy(REQUEST)
    body["lot_id"] = 1
    assert client.post("/api/v1/suppliers/search", json=body).status_code == 422
    body["lot"] = None
    assert client.post("/api/v1/suppliers/search", json=body).status_code == 200
    body["lot_id"] = None
    assert client.post("/api/v1/suppliers/search", json=body).status_code == 422


@pytest.mark.parametrize("limit,status", [("0", 422), ("-1", 422), ("1", 200), ("abc", 422)])
def test_lot_search_limit(client, monkeypatch, limit, status):
    monkeypatch.setattr(search_service, "find_lots", lambda conn, query, limit: [])
    assert client.get("/api/v1/lots/search", params={"limit": limit}).status_code == status


def test_validation_error_keys(client):
    response = client.get("/api/v1/lots/not-an-integer")
    assert response.status_code == 422
    assert set(response.json()["detail"][0]) == {"loc", "msg", "type"}
    malformed = client.post(
        "/api/v1/suppliers/search", content="{", headers={"Content-Type": "application/json"}
    )
    assert malformed.status_code == 422
    assert set(malformed.json()["detail"][0]) == {"loc", "msg", "type"}


def test_incomplete_supplier_card_is_rejected(client, monkeypatch):
    monkeypatch.setattr(enrichment_service, "supplier_card", lambda conn, inn: {"inn": inn})
    with pytest.raises(ResponseValidationError):
        client.get("/api/v1/enrichment/7802587594")


def test_supplier_card_preserves_nullable_keys(client, monkeypatch):
    card = {key: None for key in SupplierCard.model_fields}
    card.update(
        inn="7802587594",
        role="UNKNOWN",
        role_display="Роль не определена",
        okved_extra=[],
        n_bids=0,
        n_wins=0,
        n_customers=0,
        top_okpd2=[],
        recent_lots=[],
    )
    monkeypatch.setattr(enrichment_service, "supplier_card", lambda conn, inn: card)
    assert client.get("/api/v1/enrichment/7802587594").json() == card


def test_new_lot_is_promoted_to_a_complete_card(monkeypatch):
    captured = []
    engine = SimpleNamespace(
        new_lot_query=lambda lot: object(), search=lambda conn, card, *args: captured.append(card)
    )
    monkeypatch.setattr(engine_state, "engine", engine)
    # Exercise the service itself rather than the endpoint's test double.
    search_service.search(None, SearchRequest.model_validate(REQUEST))
    assert captured[0].lot_id is None
    assert captured[0].publish_date is None
    assert captured[0].actual_winners == []
    assert captured[0].okpd2_codes == ["26.20"]


def test_zero_win_rate_keeps_suppliers_without_contested_history():
    filters = SearchFilters.model_validate(FILTERS)
    assert Engine._passes(filters, None, {"contested_bids": [0]}, 0)
    filters.min_win_rate = 0.1
    assert not Engine._passes(filters, None, {"contested_bids": [0]}, 0)
