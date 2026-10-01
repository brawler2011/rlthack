import numpy as np

from app.ml.expansion import expand, learn_affinity, load_registry


class FakeConn:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, _query):
        return self

    def fetchall(self):
        return self.rows


# inn, okved_main, okved_extra, products, region, category, headcount, days since 1970
ROWS = [
    ("A", "47.11", [], ["21.20.10"], "78", 1, 5, 100),  # declares the product itself
    ("B", "46.46", [], [], "47", 1, 5, 100),  # the typical winner group, small
    ("C", "46.46", [], [], "78", 3, 900, 100),  # the same group, bigger and in SPb
    ("D", "47.73", ["46.46.1"], [], "78", 1, 5, 100),  # the group only as an additional OKVED
    ("E", "46.90", [], [], "78", 3, 900, 100),  # a rarer winner group
    ("F", "46.46", [], [], "78", 3, 900, 100),  # already known from bids
    ("G", "46.46", [], [], "78", 3, 900, 500),  # entered the registry after the lot
    ("H", "62.01", [], [], "78", 3, 900, 100),  # never wins such lots
]

# Medicines (OKPD2 21.20) are won by pharmacy wholesalers (OKVED 46.46) 3 times out of 4.
WINS = [(["21.20.10.110"], "46.46.1")] * 3 + [(["21.20.10.120"], "46.90")]


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

    assert registry.inns[rows].tolist() == ["A", "C", "B", "D", "E"]
    assert list(scores) == sorted(scores, reverse=True)
    assert reasons[0] == "заявляет выпуск продукции 21.20.10"
    assert reasons[1] == "основной ОКВЭД 46.46: такие компании выигрывают 75% похожих лотов"
    assert reasons[3].startswith("дополнительный ОКВЭД 46.46")
