"""Supplier matching engine behind the API: loaded once at startup, then answers a search in a
fraction of a second.

For a lot from the data the bidding history is cut at the start of the lot's month: the ranking
is what the service would have shown when the lot came out, and the lot's own winner is not
leaked into it. New lots typed in by the user are ranked against the whole history.
"""

import threading
import time
from dataclasses import dataclass

import numpy as np

from app.config import settings
from app.etl import pipeline
from app.ml import ranker
from app.ml.candidates import FEATURES, History, Query, load_dataset
from app.ml.expansion import affinity_from_db, expand, load_registry
from app.ml.explainer import Facts, explain
from app.ml.semantic_retriever import LotEmbeddings, encode, load_model
from app.ml.text import lot_text
from app.schemas.lot import LotCard, NewLot
from app.schemas.supplier import (
    ROLE_DISPLAY,
    NewSupplier,
    SearchFilters,
    SearchResponse,
    SupplierRecommendation,
)
from app.schemas.xai import EvidenceLot

MAX_HISTORIES = 4  # cached history snapshots (one per month of the lots looked at)
WARM_MONTHS = 3  # the latest months are prepared at startup: demo lots come from there
MAX_EVIDENCE_LOTS = 5000
EVIDENCE_PER_SUPPLIER = 3

COMPANIES_SQL = """
SELECT inn, name, role, role_reason, okved_main, okved_main_name, region_code, msp_category,
       headcount
FROM companies WHERE inn = ANY(%s)
"""
EVIDENCE_SQL = """
SELECT b.supplier_inn, l.lot_id, l.publish_date, l.subject, l.start_price::float8 AS start_price,
       b.is_winner
FROM bids b JOIN lots l USING (lot_id)
WHERE b.lot_id = ANY(%s) AND b.supplier_inn = ANY(%s)
"""
CUSTOMER_SQL = """
SELECT b.supplier_inn, count(*) FILTER (WHERE b.is_winner) AS wins, count(*) AS bids
FROM bids b JOIN lots l USING (lot_id)
WHERE l.customer_inn = %s AND l.publish_date < %s AND b.supplier_inn = ANY(%s)
GROUP BY b.supplier_inn
"""


def day_to_date(day: int):
    return np.datetime64(day, "D").astype(object)


def month_start(day: int) -> int:
    return int(np.datetime64(day, "D").astype("datetime64[M]").astype("datetime64[D]").astype(int))


@dataclass
class Snapshot:
    history: History
    known: np.ndarray  # registry rows of suppliers that already bid before the cutoff


class Engine:
    def __init__(self):
        started = time.perf_counter()
        self.emb = LotEmbeddings.load(settings.embeddings_dir)
        with pipeline.connect() as conn:
            self.data = load_dataset(conn, self.emb)
            self.registry = load_registry(conn)
            self.affinity = affinity_from_db(conn)
        self.model = ranker.load(settings.catboost_model_path)
        self.encoder = load_model()
        self.today = int(self.data.lot_day.max()) + 1
        self._snapshots: dict[int, Snapshot] = {}
        self._lock = threading.Lock()
        self.snapshot(self.today)
        for months_back in range(WARM_MONTHS):
            month = np.datetime64(self.today - 1, "D").astype("datetime64[M]") - months_back
            self.snapshot(int(month.astype("datetime64[D]").astype(int)))
        self.load_seconds = time.perf_counter() - started

    def snapshot(self, cutoff_day: int) -> Snapshot:
        with self._lock:
            if cutoff_day not in self._snapshots:
                if len(self._snapshots) >= MAX_HISTORIES:
                    oldest = next(d for d in self._snapshots if d != self.today)
                    del self._snapshots[oldest]
                history = History(self.data, self.emb, day_to_date(cutoff_day))
                known = np.isin(self.registry.inns, history.inns)
                self._snapshots[cutoff_day] = Snapshot(history, known)
            return self._snapshots[cutoff_day]

    def lot_row(self, lot_id: int) -> int | None:
        row = int(np.searchsorted(self.data.lot_ids, lot_id))
        found = row < len(self.data.lot_ids) and self.data.lot_ids[row] == lot_id
        return row if found else None

    def new_lot_query(self, lot: NewLot) -> Query:
        vector = encode(self.encoder, [lot_text(lot.subject, lot.items)])[0]
        return self.data.new_query(
            vector,
            lot.okpd2_codes,
            lot.customer_inn,
            lot.start_price,
            lot.channel,
            lot.is_smp,
            self.today,
        )

    def search(
        self,
        conn,
        card: LotCard,
        query: Query,
        okpd2_codes: list[str],
        filters: SearchFilters,
        limit: int,
        new_limit: int,
    ) -> SearchResponse:
        started = time.perf_counter()
        cutoff = month_start(query.day) if card.lot_id is not None else self.today
        snap = self.snapshot(cutoff)
        hist = snap.history
        retrieval = hist.retrieve(query)
        candidates = retrieval.candidates
        features = hist.features(query, retrieval)

        raw = self.model.predict(features) if len(candidates) else np.zeros(0)
        order = np.argsort(-raw, kind="stable")
        candidates, features, raw = candidates[order], features[order], raw[order]
        span = raw.max() - raw.min() if len(raw) else 0.0
        relevance = (raw - raw.min()) / span if span > 0 else np.ones(len(raw))

        inns = hist.inns[candidates].tolist()
        companies = {r["inn"]: r for r in conn.execute(COMPANIES_SQL, (inns,)).fetchall()}
        stats = hist.stats
        keep = [
            i
            for i, inn in enumerate(inns)
            if self._passes(filters, companies.get(inn), stats, int(candidates[i]))
        ][:limit]

        shown = [inns[i] for i in keep]
        shap = self._shap(features[keep]) if keep else np.zeros((0, len(FEATURES)))
        evidence = self._evidence(conn, retrieval, cutoff, shown)
        customer = self._customer_history(conn, card.customer_inn, cutoff, shown)
        winners = set(card.actual_winners)

        items = []
        for rank, (i, inn) in enumerate(zip(keep, shown, strict=True), start=1):
            col = int(candidates[i])
            company = companies.get(inn) or {}
            facts = self._facts(stats, col, query, card, okpd2_codes, evidence, customer, inn)
            role = company.get("role") or "UNKNOWN"
            items.append(
                SupplierRecommendation(
                    rank=rank,
                    inn=inn,
                    name=company.get("name"),
                    role=role,
                    role_display=ROLE_DISPLAY[role],
                    role_reason=company.get("role_reason"),
                    score=round(float(relevance[i]), 3),
                    win_rate=facts.win_rate,
                    n_bids=facts.bids,
                    n_wins=facts.wins,
                    avg_won_price=facts.typical_check,
                    region_code=company.get("region_code"),
                    is_spb_lo=facts.spb,
                    is_smp=bool(company) or None,
                    is_actual_winner=inn in winners,
                    explanation=explain(shap[rank - 1], facts, float(relevance[i])),
                )
            )

        new_suppliers = self._new_suppliers(conn, snap, okpd2_codes, query.day, new_limit)
        return SearchResponse(
            lot=card,
            items=items,
            new_suppliers=new_suppliers,
            total_candidates=len(candidates),
            timing_ms=round((time.perf_counter() - started) * 1000, 1),
        )

    @staticmethod
    def _passes(filters: SearchFilters, company: dict | None, stats: dict, col: int) -> bool:
        role = (company or {}).get("role") or "UNKNOWN"
        if filters.roles and role not in filters.roles:
            return False
        if filters.only_spb_lo and stats["spb_share"][col] < 0.5:
            return False
        if filters.only_smp and company is None:
            return False
        if filters.min_win_rate is not None:
            bids = stats["contested_bids"][col]
            if not bids or stats["contested_wins"][col] / bids < filters.min_win_rate:
                return False
        return True

    def _shap(self, features: np.ndarray) -> np.ndarray:
        from catboost import Pool

        pool = Pool(
            features, group_id=np.zeros(len(features), dtype=int), feature_names=list(FEATURES)
        )
        values = self.model.get_feature_importance(pool, type="ShapValues")
        return values[:, : len(FEATURES)]  # the last column is the expected value

    def _evidence(self, conn, retrieval, cutoff: int, inns: list[str]) -> dict[str, list]:
        """Past lots with the most similar texts that each supplier bid on, most similar first."""
        sim_of = dict(zip(retrieval.similar_texts.tolist(), retrieval.similar_sims.tolist()))
        rows = np.flatnonzero(
            np.isin(self.emb.lot_text_ids, retrieval.similar_texts) & (self.data.lot_day < cutoff)
        )
        if not len(rows) or not inns:
            return {}
        sims = np.array([sim_of[t] for t in self.emb.lot_text_ids[rows].tolist()])
        rows = rows[np.argsort(-sims, kind="stable")][:MAX_EVIDENCE_LOTS]
        lot_sim = {int(self.data.lot_ids[r]): sim_of[int(self.emb.lot_text_ids[r])] for r in rows}
        found: dict[str, list] = {}
        for r in conn.execute(EVIDENCE_SQL, (list(lot_sim), inns)).fetchall():
            found.setdefault(r["supplier_inn"], []).append(r)
        for lots in found.values():
            lots.sort(key=lambda r: (-lot_sim[r["lot_id"]], not r["is_winner"]))
        return found

    @staticmethod
    def _customer_history(conn, customer: str | None, cutoff: int, inns: list[str]):
        if not customer or not inns:
            return {}
        rows = conn.execute(CUSTOMER_SQL, (customer, day_to_date(cutoff), inns)).fetchall()
        return {r["supplier_inn"]: (r["wins"], r["bids"]) for r in rows}

    def _facts(self, stats, col, query, card, codes, evidence, customer, inn) -> Facts:
        lots = evidence.get(inn, [])
        contested = int(stats["contested_bids"][col])
        price = float(np.exp(stats["won_price"][col]))
        channel = self.data.channels[query.channel] if query.channel >= 0 else None
        wins, bids = customer.get(inn, (0, 0))
        since = float(query.day - stats["last_win"][col])  # inf if it never won
        return Facts(
            similar_wins=sum(r["is_winner"] for r in lots),
            similar_bids=len(lots),
            customer_wins=wins,
            customer_bids=bids,
            okpd2_group=next((c[:5] for c in codes if len(c) >= 5), None),
            wins=int(stats["wins"][col]),
            bids=int(stats["bids"][col]),
            contested_bids=contested,
            win_rate=stats["contested_wins"][col] / contested if contested else None,
            days_since_win=since if np.isfinite(since) else float("nan"),
            recent_wins=int(stats["recent_wins"][col]),
            typical_check=round(price, 2) if np.isfinite(price) else None,
            lot_price=card.start_price,
            channel=channel,
            channel_share=float(stats["channel_share"][col, query.channel])
            if query.channel >= 0
            else float("nan"),
            smp_share=float(stats["smp_share"][col]),
            spb=bool(stats["spb_share"][col] >= 0.5),
            customers=int(stats["customers"][col]),
            evidence=[
                EvidenceLot(
                    lot_id=r["lot_id"],
                    publish_date=r["publish_date"],
                    subject=r["subject"],
                    start_price=r["start_price"],
                    won=r["is_winner"],
                )
                for r in lots[:EVIDENCE_PER_SUPPLIER]
            ],
        )

    def _new_suppliers(self, conn, snap: Snapshot, codes, day: int, limit: int):
        if not limit or not codes:
            return []
        rows, scores, reasons = expand(self.registry, self.affinity, codes, snap.known, day, limit)
        inns = self.registry.inns[rows].tolist()
        companies = {r["inn"]: r for r in conn.execute(COMPANIES_SQL, (inns,)).fetchall()}
        result = []
        for inn, score, reason in zip(inns, scores.tolist(), reasons, strict=True):
            c = companies.get(inn, {})
            role = c.get("role") or "UNKNOWN"
            result.append(
                NewSupplier(
                    inn=inn,
                    name=c.get("name"),
                    role=role,
                    role_display=ROLE_DISPLAY[role],
                    okved_main=c.get("okved_main"),
                    okved_name=c.get("okved_main_name"),
                    region_code=c.get("region_code"),
                    msp_category=c.get("msp_category"),
                    headcount=c.get("headcount"),
                    reason=reason,
                    score=round(score, 3),
                )
            )
        return result


class EngineState:
    """Loads the engine in a background thread so the API starts at once."""

    def __init__(self):
        self.engine: Engine | None = None
        self.error: str | None = None
        self.loading = False

    def start(self) -> None:
        if self.loading or self.engine is not None:
            return
        self.loading = True
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self) -> None:
        try:
            self.engine = Engine()
        except Exception as error:  # reported by /health and the search endpoint
            self.error = f"{type(error).__name__}: {error}"
        finally:
            self.loading = False

    @property
    def status(self) -> str:
        if self.engine is not None:
            return "ready"
        return "loading" if self.loading else f"failed: {self.error}" if self.error else "idle"


engine_state = EngineState()
