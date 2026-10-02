from app.services.trust import is_reliable, role_from_okved, warnings

HEALTHY = {"status": "ACTIVE", "revenue": 50e6, "expenses": 40e6, "tax_debt": 0.0}


def test_no_warnings_for_a_healthy_company_or_without_data():
    assert warnings(HEALTHY, 1e6) == []
    assert warnings(None, 1e6) == [] and is_reliable(None, 1e6)


def test_warnings_name_the_problem_with_the_numbers():
    org = {"status": "INACTIVE", "revenue": 2e6, "expenses": 3e6, "tax_debt": 120_000.0}
    assert warnings(org, 1.5e6) == [
        "Компания прекратила деятельность",
        "НМЦК — 75% годовой выручки (2,0 млн ₽)",
        "Убыток за последний год: расходы 3,0 млн ₽ при доходах 2,0 млн ₽",
        "Налоговая задолженность 120 тыс. ₽",
    ]
    assert warnings({"revenue": 1e6}, 3e6) == ["НМЦК 3,0 млн ₽ больше годовой выручки (1,0 млн ₽)"]
    assert warnings({"tax_debt": 1_000.0}, None) == []  # a small late payment


def test_reliable_means_active_no_debt_and_revenue_above_the_price():
    assert is_reliable(HEALTHY, 1e6)
    assert not is_reliable({**HEALTHY, "status": "INACTIVE"}, 1e6)
    assert is_reliable({**HEALTHY, "status": "REORGANIZATION_STAGE"}, 1e6)  # only a warning
    assert not is_reliable({**HEALTHY, "tax_debt": 60_000.0}, 1e6)
    assert not is_reliable(HEALTHY, 60e6)


def test_role_from_okved_follows_the_registry_rule():
    assert role_from_okved("21.20")[0] == "MANUFACTURER"
    assert role_from_okved("46.69.8")[0] == "DISTRIBUTOR"
    assert role_from_okved("86.90")[0] == "SUPPLIER"
    assert role_from_okved(None) == ("UNKNOWN", None)
