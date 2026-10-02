"""Evidence strength, incomplete lots, and unsupported matches remain distinguishable."""

import numpy as np

from app.ml.expansion import expand, learn_affinity, load_registry
from app.services.engine import Engine
from app.services.profile_fit import assess_profile
from tests.test_expansion import FakeConn


def test_wholesaler_matches_a_goods_lot_without_being_a_manufacturer():
    fit = assess_profile(["26.20.15.000"], {"okved_main": "46.51.1"})
    assert fit.status == "PROFILE" and fit.missing_codes == []
    assert fit.evidence[0].okved_code == "46.51.1"
    assert fit.evidence[0].source == "Правила соответствия категорий сервиса"


def test_office_furniture_requires_the_office_wholesale_activity():
    assert assess_profile(["31.01.11"], {"okved_main": "46.65"}).status == "PROFILE"
    assert assess_profile(["31.01.11"], {"okved_main": "46.47.1"}).status == "UNKNOWN"


def test_additional_activity_is_valid_but_generic_trade_does_not_confirm_a_profile():
    fit = assess_profile(["26.20.15"], {"okved_main": "46.90", "okved_extra": ["46.51"]})
    assert fit.status == "PROFILE"
    assert assess_profile(["26.20.15"], {"okved_main": "46.90"}).status == "UNKNOWN"
    assert assess_profile(["26.20.15"], {"okved_main": "46.510"}).status == "UNKNOWN"


def test_partial_lot_does_not_claim_coverage_of_other_items():
    fit = assess_profile(["26.20.15", "21.20.10", "26.20.15"], {"okved_main": "46.51"})
    assert fit.covered_codes == ["26.20.15"]
    assert fit.missing_codes == ["21.20.10"]


def test_market_statistics_include_sample_size_and_do_not_claim_company_experience():
    affinity = learn_affinity([(["21.20.10"], "46.90")] * 3)
    fit = assess_profile(["21.20.10"], {"okved_main": "46.90"}, affinity)
    assert fit.status == "STATISTICAL" and fit.covered_codes == []
    assert fit.evidence[0].sample_size == 3 and fit.evidence[0].share == 1
    assert "не опыт данной компании" in fit.evidence[0].description
    assert assess_profile([], {}).status == "UNKNOWN"


def test_declared_products_and_past_wins_have_distinct_strength_and_limits():
    company = {"products": ["21.20.10"]}
    assert assess_profile(["21.20.10.110"], company).status == "PRODUCT"
    history = [{"lot_id": 7, "is_winner": True, "okpd2_codes": ["21.20.10.120"]}]
    fit = assess_profile(["21.20.10.110"], company, history=history)
    assert fit.status == "HISTORY" and fit.evidence[0].lot_ids == [7]
    assert "Исполнение контрактов" in fit.evidence[0].description
    history[0]["is_winner"] = False
    assert assess_profile(["21.20.10.110"], {}, history=history).status == "UNKNOWN"


def test_reviewed_categories_create_candidates_without_market_history():
    rows = [
        ("A", "46.51.1", [], [], "78", 1, 5, 100, []),
        ("B", "46.90", [], [], "78", 1, 5, 100, []),
        ("C", "46.51.1", [], [], "78", 1, 5, 500, []),
    ]
    registry = load_registry(FakeConn(rows))
    order, _, reasons = expand(
        registry,
        learn_affinity([]),
        ["26.20.15"],
        np.zeros(3, dtype=bool),
        day=200,
    )
    assert registry.inns[order].tolist() == ["A"]
    assert "по справочнику сервиса" in reasons[0]
    assert "не подтверждено" not in reasons[0]


def test_history_query_uses_the_requested_categories_and_cutoff():
    from datetime import date
    from types import SimpleNamespace

    calls = []

    def execute(query, parameters):
        calls.append((query, parameters))
        return SimpleNamespace(
            fetchall=lambda: [
                {"supplier_inn": "A", "lot_id": 7, "is_winner": True, "okpd2_codes": ["26.20.15"]},
            ]
        )

    found = Engine._profile_history(
        SimpleNamespace(execute=execute),
        20000,
        ["A"],
        ["26.20.15", "26.20.16"],
    )
    assert found["A"][0]["lot_id"] == 7
    assert calls[0][1] == (["A"], date(2024, 10, 4), ["26.20"])
    assert "l.publish_date < %s" in calls[0][0] and "b.is_winner" in calls[0][0]
