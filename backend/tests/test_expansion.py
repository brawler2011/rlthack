import numpy as np

from app.ml.expansion import expand, load_registry


class FakeConn:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, _query):
        return self

    def fetchall(self):
        return self.rows


# inn, okved_main, okved_extra, products, region, category, headcount, days since 1970
ROWS = [
    ("A", "46.69", [], ["28.29.31.110"], "47", 1, 5, 100),  # declares the product itself
    ("B", "28.29", [], [], "78", 1, 5, 100),  # main OKVED in the lot's group
    ("C", "47.11", ["28.29.1"], [], "78", 3, 900, 100),  # only an additional OKVED
    ("D", "28.11", [], [], "78", 1, 5, 100),  # main OKVED in the same class only
    ("E", "46.69", [], [], "78", 3, 900, 100),  # wholesale, no match
    ("F", "28.29", [], [], "78", 3, 900, 100),  # already known from bids
    ("G", "28.29", [], [], "78", 3, 900, 500),  # entered the registry after the lot
]


def test_expand_orders_by_match_strength_and_skips_known_and_later():
    registry = load_registry(FakeConn(ROWS))
    exclude = np.isin(registry.inns, ["F"])

    rows, scores, reasons = expand(registry, ["28.29.31.110"], exclude, day=200)

    assert registry.inns[rows].tolist() == ["A", "B", "C", "D"]
    assert list(scores) == sorted(scores, reverse=True)
    assert reasons[0] == "заявляет выпуск продукции с кодом 28.29.31"
    assert reasons[3] == "основной ОКВЭД в классе 28"


def test_expand_without_codes_is_empty():
    registry = load_registry(FakeConn(ROWS))
    rows, _, _ = expand(registry, [], np.zeros(len(ROWS), dtype=bool), day=200)
    assert len(rows) == 0
