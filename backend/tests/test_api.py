from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/api/v1/health").json()["status"] == "ok"


def test_search_by_lot_id_matches_the_contract():
    response = client.post("/api/v1/suppliers/search", json={"lot_id": 4760045})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"lot", "items", "new_suppliers", "total_candidates", "timing_ms"}
    item = body["items"][0]
    assert {"rank", "inn", "role", "role_display", "score", "explanation"} <= set(item)
    assert {"summary", "level", "factors", "evidence"} <= set(item["explanation"])
    assert {"inn", "role", "reason"} <= set(body["new_suppliers"][0])


def test_search_with_a_new_lot():
    lot = {"subject": "Поставка картриджей для принтеров HP", "okpd2_codes": ["20.59.12.120"]}
    response = client.post("/api/v1/suppliers/search", json={"lot": lot, "limit": 5})
    assert response.status_code == 200


def test_search_needs_exactly_one_lot():
    assert client.post("/api/v1/suppliers/search", json={}).status_code == 422
    both = {"lot_id": 1, "lot": {"subject": "Картриджи"}}
    assert client.post("/api/v1/suppliers/search", json=both).status_code == 422


def test_lots_and_supplier_card():
    assert client.get("/api/v1/lots/search", params={"query": "картридж"}).status_code == 200
    assert client.get("/api/v1/lots/4760045").json()["lot_id"] == 4760045
    card = client.get("/api/v1/enrichment/7802587594").json()
    assert card["inn"] == "7802587594" and "top_okpd2" in card
