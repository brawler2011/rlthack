from datetime import date

import numpy as np

from app.ml.candidates import FEATURES, Dataset, History, query_rows
from app.ml.semantic_retriever import LotEmbeddings


def make_data():
    # Lots 0-2 are history (days 0-2), lot 3 (day 10) is the query; lot 3 repeats lot 0's text.
    emb = LotEmbeddings(
        vectors=np.eye(2, dtype=np.float32),
        lot_ids=np.array([10, 11, 12, 13]),
        lot_text_ids=np.array([0, 0, 1, 0]),
    )
    data = Dataset(
        lot_ids=emb.lot_ids,
        lot_day=np.array([0, 1, 2, 10]),
        lot_channel=np.array([0, 0, 1, 0]),
        lot_customer=np.array([0, -1, 0, 0]),
        lot_log_price=np.log([100.0, 200.0, np.nan, 150.0]),
        lot_smp=np.array([True, False, False, True]),
        channels=np.array(["ЭМ", "АИС ГЗ"]),
        customers=np.array(["7800000001"]),
        bid_lot=np.array([0, 0, 1, 2, 3]),
        bid_inn=np.array(["A", "B", "A", "C", "A"]),
        bid_spb=np.array([True, False, True, True, True]),
        bid_win=np.array([True, False, True, True, True]),
        pref_lot=np.array([0, 1, 2, 3]),
        pref_id=np.array([0, 0, 1, 0]),
        prefix_weight=np.array([1.0, 1.0]),
    )
    return data, emb


def test_history_ranks_supplier_with_similar_wins_first():
    data, emb = make_data()
    hist = History(data, emb, date(1970, 1, 6))  # day 5

    assert hist.inns.tolist() == ["A", "B", "C"]  # the query lot's own bid is not history
    assert hist.columns(np.array(["A", "Z"])).tolist() == [0]
    assert data.winners(3).tolist() == ["A"]

    q = data.query(3, emb)
    r = hist.retrieve(q)
    assert r.candidates[0] == 0

    features = hist.features(q, r)
    assert features.shape == (len(r.candidates), len(FEATURES))
    a = dict(zip(FEATURES, features[0], strict=True))
    assert a["days_since_win"] == 9  # last win on day 1
    assert a["log_wins"] == np.float32(np.log1p(2))
    # A won lots at 100 and 200: the mean log price vs the query lot at 150
    assert np.isclose(a["price_gap"], (np.log(100) + np.log(200)) / 2 - np.log(150))


def test_query_rows_picks_lots_with_winners_in_range():
    data, _ = make_data()
    assert query_rows(data, date(1970, 1, 6), None, 10, 0).tolist() == [3]
    assert sorted(query_rows(data, date(1970, 1, 1), date(1970, 1, 3), 10, 0).tolist()) == [0, 1]
