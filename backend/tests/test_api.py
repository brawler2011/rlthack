from copy import deepcopy

import pytest
from fastapi.exceptions import ResponseValidationError
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.batch import MatchedLot
from app.schemas.lot import LotResponse
from app.schemas.supplier import SupplierProfile, SupplierSearchRequest, SupplierSearchResponse
from app.services.batch_service import batch_service
from app.services.enrichment_service import enrichment_service
from app.services.search_service import search_service

LOT = {
    "procedure_name": "Ручной подбор",
    "subject": "Ноутбуки",
    "start_price": 100000,
    "okpd2_code": "26.20",
    "is_smp": False,
    "customer_inn": None,
    "customer_kpp": None,
}
REQUEST = {
    "lot": LOT,
    "role_filter": [],
    "only_spb_lo": False,
    "only_smp": False,
    "min_win_rate": 0,
    "limit": 20,
}


@pytest.fixture
def client():
    # Do not enter the context: these API stubs need no database lifespan.
    return TestClient(app)


def test_all_endpoints_have_typed_responses_and_required_json_keys():
    schema = app.openapi()
    operations = [operation for path in schema["paths"].values() for operation in path.values()]
    assert len(operations) == 6
    assert len({operation["operationId"] for operation in operations}) == 6
    for operation in operations:
        assert "schema" in operation["responses"]["200"]["content"]["application/json"]
    for name, model in schema["components"]["schemas"].items():
        assert set(model["required"]) == set(model["properties"]), name
        assert model["additionalProperties"] is False, name


def test_health_and_empty_results(client):
    assert client.get("/api/v1/health").json() == {
        "status": "ok",
        "service": "rlthack-recsys-backend",
    }
    assert client.get("/api/v1/lots/search").json() == []
    assert client.post("/api/v1/batch/simulate").json() == {"status": "ok", "matched_lots": []}
    response = client.post("/api/v1/suppliers/search", json=REQUEST)
    assert response.status_code == 200
    assert response.json() == {"total": 0, "items": [], "inference_time_ms": 0.0}


@pytest.mark.parametrize("field", list(REQUEST))
def test_missing_request_key_is_rejected(client, field):
    body = deepcopy(REQUEST)
    del body[field]
    response = client.post("/api/v1/suppliers/search", json=body)
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "missing"


@pytest.mark.parametrize("field", list(LOT))
def test_missing_lot_key_is_rejected_even_when_nullable(client, field):
    body = deepcopy(REQUEST)
    del body["lot"][field]
    response = client.post("/api/v1/suppliers/search", json=body)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "lot", field]


@pytest.mark.parametrize("field", list(REQUEST))
def test_non_nullable_request_key_rejects_null(client, field):
    body = deepcopy(REQUEST)
    body[field] = None
    assert client.post("/api/v1/suppliers/search", json=body).status_code == 422


@pytest.mark.parametrize(
    "field", ["procedure_name", "subject", "start_price", "okpd2_code", "is_smp"]
)
def test_non_nullable_lot_key_rejects_null(client, field):
    body = deepcopy(REQUEST)
    body["lot"][field] = None
    assert client.post("/api/v1/suppliers/search", json=body).status_code == 422


@pytest.mark.parametrize("target", ["root", "lot"])
def test_unknown_fields_are_rejected(client, target):
    body = deepcopy(REQUEST)
    (body if target == "root" else body["lot"])["lot_id"] = 1
    response = client.post("/api/v1/suppliers/search", json=body)
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "extra_forbidden"


@pytest.mark.parametrize(
    "field,value",
    [
        ("min_win_rate", -0.1),
        ("min_win_rate", 1.1),
        ("limit", 0),
        ("limit", -1),
        ("role_filter", ["UNKNOWN"]),
    ],
)
def test_invalid_search_filters(client, field, value):
    body = deepcopy(REQUEST)
    body[field] = value
    assert client.post("/api/v1/suppliers/search", json=body).status_code == 422


@pytest.mark.parametrize("price,status", [(0, 200), (-1, 422)])
def test_price_boundary(client, price, status):
    body = deepcopy(REQUEST)
    body["lot"]["start_price"] = price
    assert client.post("/api/v1/suppliers/search", json=body).status_code == status


@pytest.mark.parametrize("limit,status", [("0", 422), ("-1", 422), ("1", 200), ("abc", 422)])
def test_query_limit_validation_and_conversion(client, limit, status):
    assert client.get("/api/v1/lots/search", params={"limit": limit}).status_code == status


def test_validation_errors_match_required_error_contract(client):
    response = client.get("/api/v1/lots/not-an-integer")
    assert response.status_code == 422
    for issue in response.json()["detail"]:
        assert set(issue) == {"loc", "msg", "type"}
    malformed = client.post(
        "/api/v1/suppliers/search", content="{", headers={"Content-Type": "application/json"}
    )
    assert malformed.status_code == 422
    assert set(malformed.json()["detail"][0]) == {"loc", "msg", "type"}


def test_historical_lot_requires_projection_to_search_input(client):
    lot = client.get("/api/v1/lots/123").json()
    assert set(lot) == set(LotResponse.model_fields)
    assert lot["lot_id"] == 123
    assert lot["publish_date"] is None and lot["procedure_id"] is None
    body = deepcopy(REQUEST)
    body["lot"] = lot
    assert client.post("/api/v1/suppliers/search", json=body).status_code == 422
    body["lot"] = {key: lot[key] for key in LOT}
    assert client.post("/api/v1/suppliers/search", json=body).status_code == 200


def test_enrichment_explicit_nulls(client, monkeypatch):
    empty = {
        "inn": "7802587594",
        "role": None,
        "is_gisp_manufacturer": None,
        "okved_main": None,
        "status": None,
    }
    monkeypatch.setattr(enrichment_service, "get_supplier_enrichment", lambda inn: empty)
    response = client.get("/api/v1/enrichment/7802587594")
    assert response.status_code == 200
    assert response.json() == empty


def test_incomplete_service_response_is_rejected(client, monkeypatch):
    monkeypatch.setattr(enrichment_service, "get_supplier_enrichment", lambda inn: {"inn": inn})
    with pytest.raises(ResponseValidationError):
        client.get("/api/v1/enrichment/7802587594")


def test_nonempty_search_and_batch_preserve_nullable_keys(client, monkeypatch):
    supplier = SupplierProfile(
        inn="500100732259",
        kpp=None,
        name=None,
        role="SUPPLIER",
        role_display="Поставщик",
        score=0.8,
        win_rate=0.5,
        contracts_count=1,
        avg_contract_price=100,
        is_spb_lo=False,
        is_smp=True,
        xai=None,
    )
    results = SupplierSearchResponse(total=1, items=[supplier], inference_time_ms=1)
    monkeypatch.setattr(search_service, "search", lambda request: results)
    response = client.post("/api/v1/suppliers/search", json=REQUEST)
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert set(item) == set(SupplierProfile.model_fields)
    assert item["kpp"] is None and item["name"] is None and item["xai"] is None
    lot = LotResponse(**LOT, lot_id=123, publish_date=None, procedure_id=None)
    matches = [MatchedLot(lot=lot, recommendations=results)]
    monkeypatch.setattr(batch_service, "run_daily_match", lambda: matches)
    batch = client.post("/api/v1/batch/simulate")
    assert batch.status_code == 200
    assert batch.json()["matched_lots"] == [matches[0].model_dump(mode="json")]


def test_numeric_conversion_remains_supported(client):
    body = deepcopy(REQUEST)
    body["limit"] = "20"
    body["lot"]["start_price"] = "100000"
    assert client.post("/api/v1/suppliers/search", json=body).status_code == 200


def test_request_filter_semantics():
    request = SupplierSearchRequest.model_validate(REQUEST)
    assert request.role_filter == [] and request.min_win_rate == 0
