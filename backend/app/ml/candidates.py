"""Candidate suppliers for a lot and their ranking features, from bidding history before a date.

Dataset holds everything read from the database once. History is a snapshot as of a cutoff:
retrieval matrices (similar lot texts, OKPD2 prefixes, customer) and per-supplier statistics.
A ranker trained on one snapshot is applied with a later one, the way it runs in production.
"""

import re
from dataclasses import dataclass
from datetime import date

import numpy as np

from app.ml import history
from app.ml.semantic_retriever import LotEmbeddings, similar_texts

OKPD2_LEVEL_WEIGHTS = {2: 0.25, 5: 0.5, 8: 1.0}  # by prefix length: class, group, kind
FUSION_WEIGHTS = [1.0, 0.2, 1.0]  # vectors, OKPD2, customer: picked on the offline evaluation
TOP_TEXTS = 30
TOP_PER_SOURCE = 100
SPB_LO = ("78", "47")
RECENT_DAYS = 90

FEATURES = (
    "vec_score",
    "okpd2_score",
    "customer_score",
    "fused_score",
    "vec_rank",
    "okpd2_rank",
    "customer_rank",
    "log_bids",
    "log_wins",
    "win_rate_smoothed",
    "log_contested_bids",
    "days_since_win",
    "log_recent_wins",
    "price_gap",
    "abs_price_gap",
    "channel_share",
    "smp_share",
    "smp_lot_x_share",
    "spb_share",
    "log_customers",
)

LOTS_SQL = """
SELECT lot_id, publish_date, channel, customer_inn, start_price::float8, is_smp
FROM lots ORDER BY lot_id
"""
BIDS_SQL = "SELECT lot_id, supplier_inn, supplier_kpp, is_winner FROM bids ORDER BY lot_id"
PREFIXES_SQL = """
SELECT DISTINCT i.lot_id, p.prefix
FROM lot_items i
CROSS JOIN LATERAL (VALUES (i.okpd2_l2), (i.okpd2_l4), (i.okpd2_l6)) AS p (prefix)
WHERE p.prefix IS NOT NULL
ORDER BY i.lot_id
"""


@dataclass
class Query:
    """A lot to find suppliers for: an existing one or a new one typed in by the user."""

    vector: np.ndarray
    prefixes: np.ndarray  # prefix ids
    customer: int  # -1 if unknown
    log_price: float  # NaN if unknown
    channel: int  # -1 if unknown
    smp: bool
    day: int  # days since 1970-01-01


@dataclass
class Dataset:
    lot_ids: np.ndarray  # sorted, the same order as the embeddings
    lot_day: np.ndarray
    lot_channel: np.ndarray  # code into channels
    lot_customer: np.ndarray  # code into customers, -1 if unknown
    lot_log_price: np.ndarray
    lot_smp: np.ndarray
    channels: np.ndarray
    customers: np.ndarray
    bid_lot: np.ndarray  # lot row, sorted
    bid_inn: np.ndarray
    bid_spb: np.ndarray  # supplier registered in Saint Petersburg or Leningrad Region
    bid_win: np.ndarray
    pref_lot: np.ndarray  # (lot row, prefix id) pairs, sorted by lot row
    pref_id: np.ndarray
    prefix_weight: np.ndarray  # OKPD2 level weight per prefix id
    prefixes: np.ndarray | None = None  # prefix string per prefix id

    def bidders(self, row: int) -> np.ndarray:
        a, b = np.searchsorted(self.bid_lot, [row, row + 1])
        return self.bid_inn[a:b]

    def winners(self, row: int) -> np.ndarray:
        a, b = np.searchsorted(self.bid_lot, [row, row + 1])
        return self.bid_inn[a:b][self.bid_win[a:b]]

    def prefix_ids(self, okpd2_codes: list[str]) -> np.ndarray:
        """Ids of the class / group / kind prefixes of the codes that exist in the data."""
        found = set()
        for code in okpd2_codes:
            for pattern in _PREFIX_PATTERNS:
                if (m := pattern.match(code.strip())) is not None:
                    i = np.searchsorted(self.prefixes, m.group())
                    if i < len(self.prefixes) and self.prefixes[i] == m.group():
                        found.add(int(i))
        return np.array(sorted(found), dtype=np.int64)

    def new_query(
        self,
        vector: np.ndarray,
        okpd2_codes: list[str],
        customer_inn: str | None,
        start_price: float | None,
        channel: str | None,
        smp: bool,
        day: int,
    ) -> Query:
        """A query for a lot that is not in the data."""

        def code(values: np.ndarray, value: str | None) -> int:
            i = np.searchsorted(values, value or "")
            return int(i) if value and i < len(values) and values[i] == value else -1

        return Query(
            vector=vector,
            prefixes=self.prefix_ids(okpd2_codes),
            customer=code(self.customers, customer_inn),
            log_price=float(np.log(start_price)) if start_price and start_price > 0 else np.nan,
            channel=code(self.channels, channel),
            smp=smp,
            day=day,
        )

    def query(self, row: int, emb: LotEmbeddings) -> Query:
        a, b = np.searchsorted(self.pref_lot, [row, row + 1])
        return Query(
            vector=emb.vectors[emb.lot_text_ids[row]],
            prefixes=self.pref_id[a:b],
            customer=int(self.lot_customer[row]),
            log_price=float(self.lot_log_price[row]),
            channel=int(self.lot_channel[row]),
            smp=bool(self.lot_smp[row]),
            day=int(self.lot_day[row]),
        )


# The same prefixes as okpd2_prefix() in schema.sql: class, group, kind.
_PREFIX_PATTERNS = [re.compile(p) for p in (r"^\d{2}", r"^\d{2}\.\d{2}", r"^\d{2}\.\d{2}\.\d{2}")]


def _codes(values: list[str | None]) -> tuple[np.ndarray, np.ndarray]:
    """Unique non-empty values and a code per input, -1 for empty."""
    uniques, codes = np.unique(np.array([v or "" for v in values]), return_inverse=True)
    if len(uniques) and uniques[0] == "":
        return uniques[1:], codes - 1
    return uniques, codes


def load_dataset(conn, emb: LotEmbeddings) -> Dataset:
    lots = conn.execute(LOTS_SQL).fetchall()
    lot_ids = np.array([r[0] for r in lots], dtype=np.int64)
    if not np.array_equal(lot_ids, emb.lot_ids):
        raise RuntimeError(
            "Embeddings are out of sync with the database: rerun 04_build_embeddings"
        )
    channels, lot_channel = _codes([r[2] for r in lots])
    customers, lot_customer = _codes([r[3] for r in lots])
    price = np.array([r[4] if r[4] and r[4] > 0 else np.nan for r in lots])

    bids = conn.execute(BIDS_SQL).fetchall()
    spb = [(kpp or inn)[:2] in SPB_LO for _, inn, kpp, _ in bids]

    pairs = conn.execute(PREFIXES_SQL).fetchall()
    prefixes, pref_id = np.unique(np.array([p for _, p in pairs]), return_inverse=True)
    level = np.char.str_len(prefixes)

    return Dataset(
        lot_ids=lot_ids,
        lot_day=np.array([r[1] for r in lots], dtype="datetime64[D]").astype(np.int64),
        lot_channel=lot_channel,
        lot_customer=lot_customer,
        lot_log_price=np.log(price),
        lot_smp=np.array([bool(r[5]) for r in lots]),
        channels=channels,
        customers=customers,
        bid_lot=np.searchsorted(lot_ids, [b[0] for b in bids]),
        bid_inn=np.array([b[1] for b in bids]),
        bid_spb=np.array(spb),
        bid_win=np.array([b[3] for b in bids]),
        pref_lot=np.searchsorted(lot_ids, [lot for lot, _ in pairs]),
        pref_id=pref_id,
        prefix_weight=np.vectorize(lambda n: OKPD2_LEVEL_WEIGHTS.get(n, 0.0))(level),
        prefixes=prefixes,
    )


@dataclass
class Retrieval:
    scores: list[np.ndarray]  # per source: vectors, OKPD2, customer
    rankings: list[np.ndarray]  # per source, best first
    fused: np.ndarray  # weighted reciprocal rank fusion of the rankings
    candidates: np.ndarray  # top suppliers by the fused score
    similar_texts: np.ndarray  # rows of the most similar past lot texts, for explanations
    similar_sims: np.ndarray


class History:
    """Bids before the cutoff: retrieval matrices and per-supplier statistics."""

    def __init__(self, data: Dataset, emb: LotEmbeddings, cutoff: date):
        self.data, self.emb = data, emb
        self.cutoff_day = int(np.datetime64(cutoff, "D").astype(np.int64))
        keep = data.lot_day[data.bid_lot] < self.cutoff_day
        lot, win = data.bid_lot[keep], data.bid_win[keep]
        self.inns, col = np.unique(data.bid_inn[keep], return_inverse=True)
        n = len(self.inns)

        self.by_text = history.key_matrix(emb.lot_text_ids[lot], col, win, len(emb.vectors), n)
        self.by_okpd2 = self._okpd2_matrix(lot, col, win, n)
        known = data.lot_customer[lot] >= 0
        self.by_customer = history.key_matrix(
            data.lot_customer[lot][known], col[known], win[known], len(data.customers), n
        )
        self.stats = self._supplier_stats(lot, col, win, data.bid_spb[keep], n)

    def columns(self, inns: np.ndarray) -> np.ndarray:
        """Columns of the given INNs that exist in this history."""
        idx = np.searchsorted(self.inns, inns)
        idx = idx[idx < len(self.inns)]
        return idx[np.isin(self.inns[idx], inns)]

    def _okpd2_matrix(self, lot, col, win, n):
        d = self.data
        counts = np.bincount(d.pref_lot, minlength=len(d.lot_ids))
        starts = np.cumsum(counts) - counts
        reps = counts[lot]
        bid = np.repeat(np.arange(len(lot)), reps)
        offset = np.arange(reps.sum()) - np.repeat(np.cumsum(reps) - reps, reps)
        prefix = d.pref_id[starts[lot][bid] + offset]
        return history.key_matrix(prefix, col[bid], win[bid], len(d.prefix_weight), n)

    def _supplier_stats(self, lot, col, win, spb, n) -> dict[str, np.ndarray]:
        d = self.data
        day = d.lot_day[lot]

        def total(weights=None):
            return np.bincount(col, weights=weights, minlength=n).astype(float)

        bids = total()
        contested = (np.bincount(lot, minlength=len(d.lot_ids)) > 1)[lot]
        contested_bids, contested_wins = total(contested), total(contested & win)
        prior = contested_wins.sum() / max(contested_bids.sum(), 1.0)
        last_win = np.full(n, -np.inf)
        np.maximum.at(last_win, col[win], day[win])
        price = d.lot_log_price[lot]
        priced = win & ~np.isnan(price)
        with np.errstate(invalid="ignore", divide="ignore"):
            won_price = total(np.where(priced, price, 0.0)) / total(priced)
        has_customer = d.lot_customer[lot] >= 0
        pairs = np.unique(col[has_customer] * len(d.customers) + d.lot_customer[lot][has_customer])
        return {
            "bids": bids,
            "wins": total(win),
            "contested_bids": contested_bids,
            "contested_wins": contested_wins,
            "win_rate": (contested_wins + 5 * prior) / (contested_bids + 5),
            "last_win": last_win,
            "recent_wins": total(win & (day >= self.cutoff_day - RECENT_DAYS)),
            "won_price": won_price,
            "channel_share": np.stack(
                [total(d.lot_channel[lot] == c) for c in range(len(d.channels))], axis=1
            )
            / bids[:, None],
            "smp_share": total(d.lot_smp[lot]) / bids,
            "spb_share": total(spb) / bids,
            "customers": np.bincount(pairs // len(d.customers), minlength=n).astype(float),
        }

    def retrieve(self, q: Query) -> Retrieval:
        rows, sims = similar_texts(self.emb.vectors, q.vector, TOP_TEXTS)
        customer = np.array([q.customer] if q.customer >= 0 else [], dtype=int)
        scores = [
            history.score(self.by_text, rows, np.clip(sims, 0, None)),
            history.score(self.by_okpd2, q.prefixes, self.data.prefix_weight[q.prefixes]),
            history.score(self.by_customer, customer, np.ones(len(customer))),
        ]
        rankings = [history.top_suppliers(s, TOP_PER_SOURCE) for s in scores]
        fused = history.reciprocal_rank_fusion(rankings, len(self.inns), FUSION_WEIGHTS)
        candidates = history.top_suppliers(fused, TOP_PER_SOURCE)
        return Retrieval(scores, rankings, fused, candidates, rows, sims)

    def features(self, q: Query, r: Retrieval) -> np.ndarray:
        """(candidates x FEATURES) matrix; NaN where a value is unknown."""
        c, s = r.candidates, self.stats
        ranks = []
        for ranking in r.rankings:
            rank = np.full(len(self.inns), TOP_PER_SOURCE + 1.0)
            rank[ranking] = np.arange(1, len(ranking) + 1)
            ranks.append(rank[c])
        since = q.day - s["last_win"][c]
        gap = s["won_price"][c] - q.log_price
        channel = s["channel_share"][c, q.channel] if q.channel >= 0 else np.full(len(c), np.nan)
        columns = [
            *(score[c] for score in r.scores),
            r.fused[c],
            *ranks,
            np.log1p(s["bids"][c]),
            np.log1p(s["wins"][c]),
            s["win_rate"][c],
            np.log1p(s["contested_bids"][c]),
            np.where(np.isfinite(since), since, np.nan),
            np.log1p(s["recent_wins"][c]),
            gap,
            np.abs(gap),
            channel,
            s["smp_share"][c],
            s["smp_share"][c] * q.smp,
            s["spb_share"][c],
            np.log1p(s["customers"][c]),
        ]
        return np.column_stack(columns).astype(np.float32)


def query_rows(data: Dataset, start: date, end: date | None, n: int, seed: int) -> np.ndarray:
    """Up to n random lot rows published in [start, end) that have a known winner."""
    rows = np.unique(data.bid_lot[data.bid_win])
    days = data.lot_day[rows]
    in_range = days >= np.datetime64(start, "D").astype(np.int64)
    if end is not None:
        in_range &= days < np.datetime64(end, "D").astype(np.int64)
    rows = rows[in_range]
    return np.random.default_rng(seed).choice(rows, size=min(n, len(rows)), replace=False)
