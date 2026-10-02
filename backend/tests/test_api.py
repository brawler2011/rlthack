import os

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app.core.database import get_db
from app.etl import pipeline
from app.main import app

requires_db = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not set"
)
client = TestClient(app)  # no lifespan: no DB pool, the engine is not loaded


@pytest.fixture
def no_db():
    app.dependency_overrides[get_db] = lambda: None
    yield
    app.dependency_overrides.clear()


def test_health_reports_the_engine():
    body = client.get("/api/v1/health").json()
    assert body["status"] == "ok" and body["engine"] == "idle"


def test_search_waits_for_the_engine(no_db):
    response = client.post(
        "/api/v1/suppliers/search",
        json={
            "lot_id": 1,
            "lot": None,
            "filters": {
                "roles": [],
                "only_spb_lo": False,
                "only_smp": False,
                "min_win_rate": 0,
                "only_reliable": False,
            },
            "limit": 20,
            "new_limit": 10,
        },
    )
    assert response.status_code == 503


def test_batch_waits_for_the_engine(no_db, monkeypatch):
    lot = {
        "lot_id": 1,
        "publish_date": None,
        "subject": "x",
        "start_price": None,
        "channel": None,
        "customer_inn": None,
    }

    class Conn:
        def execute(self, *_):
            return self

        def fetchall(self):
            return [lot]

    app.dependency_overrides[get_db] = lambda: Conn()
    assert client.post("/api/v1/batch/simulate").status_code == 503


def test_search_needs_exactly_one_lot(no_db):
    assert client.post("/api/v1/suppliers/search", json={}).status_code == 422
    both = {"lot_id": 1, "lot": {"subject": "Картриджи"}}
    assert client.post("/api/v1/suppliers/search", json=both).status_code == 422


@pytest.fixture
def api_db(db):
    """The test dataset plus one registry company; the API reads it through get_db."""
    pipeline.run_sql_file(db, "companies_schema.sql")
    db.execute(
        "INSERT INTO companies VALUES ('7802587594', 'ООО «ВЕСЫ»', false, '78', 1, 12, "
        "'2016-08-10', '28.29', 'Производство прочих машин', '{46.69}', '{}', '{}', 'rmsp', "
        "NULL, NULL, NULL)"
    )
    pipeline.run_sql_file(db, "companies.sql")
    db.commit()

    def conn():
        with psycopg.connect(os.environ["TEST_DATABASE_URL"], row_factory=dict_row) as c:
            yield c

    app.dependency_overrides[get_db] = conn
    yield
    app.dependency_overrides.clear()


@requires_db
def test_lots(api_db):
    found = client.get("/api/v1/lots/search", params={"query": "картридж"}).json()
    assert [lot["lot_id"] for lot in found] == [3]
    assert client.get("/api/v1/lots/search", params={"query": "1"}).json()[0]["lot_id"] == 1

    card = client.get("/api/v1/lots/1").json()
    assert card["okpd2_codes"] == ["17.12.14.110"]
    assert card["actual_winners"] == ["7802587594"]
    assert client.get("/api/v1/lots/404").status_code == 404


@requires_db
def test_supplier_card(api_db):
    card = client.get("/api/v1/enrichment/7802587594").json()
    assert (card["name"], card["role"], card["okved_main"]) == (
        "ООО «ВЕСЫ»",
        "MANUFACTURER",
        "28.29",
    )
    assert (card["n_bids"], card["n_wins"]) == (3, 2)
    assert card["top_okpd2"][0]["prefix"] in {"17.12", "33.12", "20.59"}
    assert len(card["recent_lots"]) == 3

    history_only = client.get("/api/v1/enrichment/7811383967").json()
    assert history_only["role"] == "UNKNOWN" and history_only["n_bids"] == 2
    assert client.get("/api/v1/enrichment/0000000000").status_code == 404


@requires_db
def test_supplier_card_outside_the_registry_from_fns_data(api_db, db):
    """Name, role by OKVED and reliability of a supplier outside the SME registry."""
    pipeline.run_sql_file(db, "organizations_schema.sql")
    db.execute(
        "INSERT INTO organizations (inn, name, okved, status, revenue, expenses, tax_debt, source) "
        "VALUES ('7811383967', 'ООО «ОПТ»', '46.69.8', 'ACTIVE', 2e6, 3e6, 0, 'egrul')"
    )
    db.commit()
    try:
        card = client.get("/api/v1/enrichment/7811383967").json()
        assert (card["name"], card["role"], card["okved_main"]) == (
            "ООО «ОПТ»",
            "DISTRIBUTOR",
            "46.69.8",
        )
        assert card["trust"]["revenue"] == 2e6
        assert card["trust"]["warnings"] == [
            "Убыток за последний год: расходы 3,0 млн ₽ при доходах 2,0 млн ₽"
        ]
        assert client.get("/api/v1/enrichment/7802587594").json()["trust"] is None
    finally:
        db.execute("DROP TABLE organizations")
        db.commit()
