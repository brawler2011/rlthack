import pytest

from app.services.trust import is_reliable, reliability_factor, role_from_okved, warnings

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
    assert warnings({"revenue": 100e6, "expenses": 105e6}, None) == []  # about break-even


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
    assert role_from_okved(None, 'СПБ ГБУЗ "ГОРОДСКАЯ ДЕЗИНФЕКЦИОННАЯ СТАНЦИЯ"')[0] == "SUPPLIER"
    assert role_from_okved(None, 'ФБУЗ "ЦЕНТР ГИГИЕНЫ"')[0] == "SUPPLIER"
    assert role_from_okved(None, 'ООО "ГБУ ТРЕЙД"')[0] == "UNKNOWN"


@pytest.mark.parametrize(
    "org,price,factor",
    [
        (None, 1e6, 1),
        ({"revenue": None, "status": None, "tax_debt": None}, 1e6, 1),
        (HEALTHY, 1e6, 1),
        ({"tax_debt": 49_999}, None, 1),
        ({"tax_debt": 50_000}, None, 0.75),
        ({"status": "INACTIVE"}, None, 0.1),
        ({"status": "BANKRUPTCY_STAGE"}, None, 0.1),
        ({"status": "LIQUIDATION_STAGE"}, None, 0.1),
        ({"status": "REORGANIZATION_STAGE"}, None, 0.9),
        ({"revenue": 2e6}, 1e6, 0.8),
        ({"revenue": 2e6}, 2e6, 0.5),
        ({"revenue": 0}, 1e6, 0.5),
        ({"revenue": 0}, None, 1),
        ({"revenue": 2e6, "expenses": 2.2e6}, None, 1),
        ({"revenue": 2e6, "expenses": 3e6}, None, 0.85),
        ({"revenue": 2e6, "expenses": 3e6, "tax_debt": 50_000}, 3e6, 0.31875),
    ],
)
def test_current_risks_discount_scores_without_penalizing_unknown_data(org, price, factor):
    assert reliability_factor(org, price) == pytest.approx(factor)


def test_tax_offence_fine_is_visible_without_double_counting_the_debt_penalty():
    org = {"tax_debt": 60000, "tax_fines": 60000}
    assert len(warnings(org, None)) == 2
    assert reliability_factor(org, None) == 0.75
    assert reliability_factor({"tax_fines": 60000}, None) == 0.75
    assert not is_reliable({"tax_fines": 60000}, None)
    assert warnings({"tax_fines": 1000}, None)
