"""Current FNS risks affect ordering, selection limits and online thresholds."""

from types import SimpleNamespace

import numpy as np
import pytest

from app.ml.expansion import learn_affinity, load_registry
from app.schemas.lot import LotCard
from app.schemas.supplier import SearchFilters
from app.services import engine as engine_module
from app.services.engine import Engine
from tests.test_csv_batch import make_engine


def test_historical_candidates_are_reranked_before_limits_and_automatic_threshold(monkeypatch):
    engine = make_engine([10, 9, 0])
    engine.has_organizations = True
    monkeypatch.setattr(
        engine_module, "trust_rows", lambda *args: {"7800000000": {"tax_debt": 100_000}}
    )
    card = LotCard(
        subject="Бумага",
        items=[],
        okpd2_codes=[],
        start_price=1000,
        customer_inn=None,
        channel=None,
        is_smp=False,
        lot_id=None,
        publish_date=None,
        procedure_name=None,
        actual_winners=[],
    )
    conn = SimpleNamespace(execute=lambda *args: SimpleNamespace(fetchall=lambda: []))
    filters = SearchFilters(
        roles=[], only_spb_lo=False, only_smp=False, min_win_rate=0, only_reliable=False
    )
    result = engine.search(conn, card, SimpleNamespace(day=1), [], filters, 1, 0)
    assert result.items[0].inn == "7800000001"
    assert result.items[0].score == 0.9
    result = engine.search(conn, card, SimpleNamespace(day=1), [], filters, 100, 0)
    debtor = result.items[1]
    assert (debtor.base_score, debtor.score, debtor.reliability_factor) == (1, 0.75, 0.75)
    assert debtor.rank == 2 and debtor.warnings
    # All candidates have a risk: none are promoted back to 1 by renormalization.
    monkeypatch.setattr(
        engine_module,
        "trust_rows",
        lambda conn, inns: {inn: {"status": "INACTIVE"} for inn in inns},
    )
    result = engine.search(conn, card, SimpleNamespace(day=1), [], filters, 100, 0, automatic=True)
    assert result.items == []


@pytest.mark.parametrize(
    "has_data,only_reliable,expected", [(True, False, "B"), (True, True, "B"), (False, False, "A")]
)
def test_registry_risks_are_applied_to_the_full_pool_before_the_limit(
    monkeypatch, has_data, only_reliable, expected
):
    rows = [
        ("A", "46.46", [], ["21.20.10"], "78", 1, 5, 100, []),
        ("B", "46.46", [], ["21.20.10"], "78", 1, 4, 100, []),
    ]
    conn = SimpleNamespace(execute=lambda *args: SimpleNamespace(fetchall=lambda: rows))
    engine = object.__new__(Engine)
    engine.registry = load_registry(conn)
    engine.affinity = learn_affinity([(["21.20.10"], "46.46")])
    engine.licenses = None
    engine.has_organizations = has_data
    monkeypatch.setattr(
        engine_module, "trust_rows", lambda *args: {"A": {"revenue": 0, "tax_debt": 60_000}}
    )
    conn = SimpleNamespace(execute=lambda *args: SimpleNamespace(fetchall=lambda: []))
    snap = SimpleNamespace(known=np.zeros(2, dtype=bool))
    found = engine._new_suppliers(conn, snap, ["21.20.10"], 200, 1, 1e6, only_reliable)
    assert [s.inn for s in found] == [expected]
    assert found[0].score == found[0].base_score == 1
    if has_data and not only_reliable:
        found = engine._new_suppliers(conn, snap, ["21.20.10"], 200, 2, 1e6)
        assert found[1].score == 0.375 and found[1].warnings
        assert found[1].reason == "заявляет выпуск продукции 21.20.10"
