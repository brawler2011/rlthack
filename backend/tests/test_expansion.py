import numpy as np
import pytest

from app.ml.expansion import (
    Affinity,
    expand,
    learn_affinity,
    learn_license_affinity,
    load_registry,
    short_license,
)


class FakeConn:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, _query):
        return self

    def fetchall(self):
        return self.rows


PHARMACY = "фармацевтическая деятельность"

# inn, okved_main, okved_extra, products, region, category, headcount, days since 1970, licenses
ROWS = [
    ("A", "47.11", [], ["21.20.10"], "78", 1, 5, 100, []),  # declares the product itself
    ("B", "46.46", [], [], "47", 1, 5, 100, [PHARMACY]),  # the typical winner group, small
    ("C", "46.46", [], [], "78", 3, 900, 100, []),  # the same group, bigger and in SPb
    ("D", "47.73", ["46.46.1"], [], "78", 1, 5, 100, []),  # 46.46 as an additional OKVED
    ("E", "46.90", [], [], "78", 3, 900, 100, []),  # a rarer winner group, alone in it
    ("F", "46.46", [], [], "78", 3, 900, 100, []),  # already known from bids
    ("G", "46.46", [], [], "78", 3, 900, 500, []),  # entered the registry after the lot
    ("H", "62.01", [], [], "78", 3, 900, 100, []),  # never wins such lots
    ("I", "46.46", [], [], "77", 3, 900, 100, []),  # another region: in the table as a bidder
]

# Medicines (OKPD2 21.20) are won by pharmacy wholesalers (OKVED 46.46) 3 times out of 4.
WINS = [(["21.20.10.110"], "46.46.1")] * 3 + [(["21.20.10.120"], "46.90")]
# A pharmacy license: 1 of 4 medicine wins, 1 of 14 overall. An education license is as
# common among software winners, so it says nothing about medicines.
EDUCATION = "образовательная деятельность"
LICENSE_WINS = (
    [(["21.20.10.110"], [PHARMACY]), (["21.20.10.110"], [EDUCATION])]
    + [(["21.20.10.120"], [])] * 2
    + [(["62.01.11"], [EDUCATION])] * 5
    + [(["62.01.12"], [])] * 5
)

# A typical group, a rare main group, and the same rare group as an additional OKVED.
PROFILE_ROWS = [
    ("A", "46.46", ["62.01"], [], "78", 1, 5, 100, []),
    ("B", "46.90", ["62.01"], [], "78", 1, 5, 100, []),
    ("C", "62.01", ["46.90"], [], "78", 1, 5, 100, []),
]


@pytest.mark.parametrize("explain", [True, False])
def test_expand_excludes_weak_main_and_additional_okved_matches(explain):
    registry = load_registry(FakeConn(PROFILE_ROWS))
    affinity = learn_affinity([(["21.20.10"], "46.46")] * 199 + [(["21.20.10"], "46.90")])

    rows, scores, reasons = expand(
        registry, affinity, ["21.20.10"], np.zeros(3, dtype=bool), day=200, explain=explain
    )

    assert registry.inns[rows].tolist() == ["A"]
    assert scores.tolist() == [1.0]
    assert reasons == (
        [
            "основной ОКВЭД 46.46: такие компании выигрывают 100% похожих лотов; "
            "1 из 2 групп ОКВЭД компании — по профилю лота"
        ]
        if explain
        else []
    )


@pytest.mark.parametrize("share,expected", [(0.049, []), (0.05, ["B", "C"])])
def test_expand_uses_the_profile_threshold_for_eligibility_and_explanation(share, expected):
    # Isolate learned eligibility: 46.46 can also qualify through the curated goods rule.
    registry = load_registry(FakeConn(PROFILE_ROWS[1:]))
    affinity = Affinity({"21.20": {"46.90": share}})

    rows, _, reasons = expand(registry, affinity, ["21.20.10"], np.zeros(2, dtype=bool), day=200)

    assert registry.inns[rows].tolist() == expected
    assert all("1 из 2 групп ОКВЭД компании — по профилю лота" in reason for reason in reasons)


def test_small_rare_group_cannot_displace_supported_companies():
    # Without the eligibility threshold, the rare group's 4% goes to one company,
    # giving it a higher score than each of the 50 companies splitting the other 96%.
    registry = load_registry(
        FakeConn([(f"A{i}", *PROFILE_ROWS[0][1:]) for i in range(50)] + [PROFILE_ROWS[1]])
    )
    affinity = learn_affinity([(["21.20.10"], "46.46")] * 96 + [(["21.20.10"], "46.90")] * 4)

    rows, _, reasons = expand(
        registry, affinity, ["21.20.10"], np.zeros(51, dtype=bool), day=200, top=3
    )

    assert len(rows) == 3
    assert registry.main_group[rows].tolist() == ["46.46"] * 3
    assert all("1 из 2 групп ОКВЭД компании — по профилю лота" in reason for reason in reasons)


@pytest.mark.parametrize("extra", [[], ["47.11"]])
def test_expand_explains_product_and_license_matches_without_fitting_okved(extra):
    registry = load_registry(
        FakeConn(
            [
                ("A", "62.01", extra, ["21.20.10"], "78", 1, 5, 100, []),
                ("B", "62.01", extra, [], "78", 1, 5, 100, [PHARMACY]),
                ("C", "62.01", extra, [], "78", 1, 5, 100, []),
            ]
        )
    )

    rows, scores, reasons = expand(
        registry,
        Affinity({}),
        ["21.20.10"],
        np.zeros(3, dtype=bool),
        day=200,
        licenses=learn_license_affinity(LICENSE_WINS),
    )

    assert registry.inns[rows].tolist() == ["A", "B"]
    assert scores.tolist() == [1.0, 0.25]
    assert reasons == [
        "заявляет выпуск продукции 21.20.10; соответствие ОКВЭД профилю лота не подтверждено",
        "лицензия «фармацевтическая деятельность»: её владельцы выигрывают 25% похожих лотов; "
        "соответствие ОКВЭД профилю лота не подтверждено",
    ]


def test_learn_affinity_shares_by_group_with_class_backoff():
    affinity = learn_affinity(WINS + [(["21.10.1"], None)])
    assert affinity.for_codes(["21.20.10.190"]) == {"46.46": 0.75, "46.90": 0.25}
    assert affinity.for_codes(["21.10.60"]) == {"46.46": 0.75, "46.90": 0.25}  # class 21
    assert affinity.for_codes(["62.01.11"]) == {}


def test_expand_orders_by_learned_fit_and_skips_known_and_later():
    registry = load_registry(FakeConn(ROWS))
    affinity = learn_affinity(WINS)

    rows, scores, reasons = expand(
        registry, affinity, ["21.20.10.190"], np.isin(registry.inns, ["F"]), day=200
    )

    # A declares the product (1.0), but its only OKVED group does not fit the lot: x0.75.
    # B and C split 75% of the wins of 46.46 (F is known, G is later, I is from another
    # region): 0.375 each, all their OKVED fits. D alone has 46.46 as an additional OKVED:
    # 0.375, but only 1 of its 2 groups fits: x0.875. E alone in 46.90: 0.25.
    assert registry.inns[rows].tolist() == ["A", "C", "B", "D", "E"]
    expected = np.array([0.75, 0.375, 0.375, 0.375 * 0.875, 0.25]) / 0.75  # relative to A
    assert np.allclose(scores, expected)
    assert reasons[0] == (
        "заявляет выпуск продукции 21.20.10; соответствие ОКВЭД профилю лота не подтверждено"
    )
    assert reasons[1] == "основной ОКВЭД 46.46: такие компании выигрывают 75% похожих лотов"
    assert reasons[3] == (
        "дополнительный ОКВЭД 46.46: такие компании выигрывают 75% похожих лотов; "
        "1 из 2 групп ОКВЭД компании — по профилю лота"
    )


def test_license_fit_keeps_licenses_specific_to_the_lot():
    licenses = learn_license_affinity(LICENSE_WINS)
    assert licenses.for_codes(["21.20.10.190"]) == {PHARMACY: 0.25}
    assert licenses.for_codes(["62.01.11"]) == {}


def test_license_lifts_its_holders_within_a_group():
    registry = load_registry(FakeConn(ROWS))
    licenses = learn_license_affinity(LICENSE_WINS)

    rows, scores, reasons = expand(
        registry,
        learn_affinity(WINS),
        ["21.20.10.190"],
        np.isin(registry.inns, ["F"]),
        day=200,
        licenses=licenses,
    )

    assert registry.inns[rows].tolist() == ["A", "B", "C", "D", "E"]
    # its group's share per company plus the license's, relative to A (0.75, see above)
    assert np.isclose(scores[1], (0.75 / 2 + 0.25) / 0.75)
    assert reasons[1] == (
        "основной ОКВЭД 46.46: такие компании выигрывают 75% похожих лотов; "
        "лицензия «фармацевтическая деятельность»: её владельцы выигрывают 25% похожих лотов"
    )


def test_short_license_drops_clarifications():
    assert (
        short_license(
            "медицинская деятельность (за исключением указанной деятельности, осуществляемой "
            "медицинскими организациями (в том числе частными))"
        )
        == "медицинская деятельность"
    )
    assert short_license("образовательная деятельность, осуществляемая организациями") == (
        "образовательная деятельность"
    )
    assert short_license("размещение отходов i - iv классов опасности") == (
        "размещение отходов I - IV классов опасности"
    )
