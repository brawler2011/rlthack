"""Script 06: Offline evaluation of supplier recommendations on a time split.

History = lots published before the cutoff; queries = later lots with a known winner.
Metrics: share of queries with the actual winner in the top K (Recall@K) and MRR@20.
"""

import argparse
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from app.config import settings  # noqa: E402
from app.etl import pipeline  # noqa: E402
from app.ml import history  # noqa: E402
from app.ml.semantic_retriever import LotEmbeddings, similar_texts  # noqa: E402

KS = (1, 5, 10, 20)
OKPD2_LEVEL_WEIGHTS = {2: 0.25, 5: 0.5, 8: 1.0}  # by prefix length: class, group, kind

LOT_PREFIXES = """
SELECT DISTINCT i.lot_id, p.prefix
FROM lot_items i
CROSS JOIN LATERAL (VALUES (i.okpd2_l2), (i.okpd2_l4), (i.okpd2_l6)) AS p (prefix)
WHERE p.prefix IS NOT NULL
"""


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cutoff", type=date.fromisoformat, default=date(2025, 10, 1))
    parser.add_argument("--queries", type=int, default=2000)
    parser.add_argument("--top-texts", type=int, default=50, help="similar texts per query")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main():
    args = parse_args()
    emb = LotEmbeddings.load(settings.embeddings_dir)
    lot_row = {lot_id: i for i, lot_id in enumerate(emb.lot_ids.tolist())}

    with pipeline.connect() as conn, pipeline.timed("[06] Reading history"):
        lots = {r[0]: r[1:] for r in conn.execute("SELECT lot_id, publish_date, channel FROM lots")}
        bids = conn.execute("SELECT lot_id, supplier_inn, is_winner FROM bids").fetchall()
        lot_prefixes = defaultdict(list)
        for lot_id, prefix in conn.execute(LOT_PREFIXES):
            lot_prefixes[lot_id].append(prefix)

    train = [b for b in bids if lots[b[0]][0] < args.cutoff]
    inns = np.unique([b[1] for b in train])
    col = {inn: i for i, inn in enumerate(inns)}
    prefixes = sorted({p for ps in lot_prefixes.values() for p in ps})
    prefix_row = {p: i for i, p in enumerate(prefixes)}

    with pipeline.timed("[06] Building history matrices"):
        lot_col = np.array([col[b[1]] for b in train])
        wins = np.array([b[2] for b in train])
        text_keys = emb.lot_text_ids[[lot_row[b[0]] for b in train]]
        by_text = history.key_matrix(text_keys, lot_col, wins, len(emb.vectors), len(inns))
        pk, ps, pw = [], [], []
        for (lot_id, _, win), c in zip(train, lot_col, strict=True):
            for p in lot_prefixes.get(lot_id, ()):
                pk.append(prefix_row[p])
                ps.append(c)
                pw.append(win)
        by_okpd2 = history.key_matrix(
            np.array(pk), np.array(ps), np.array(pw), len(prefixes), len(inns)
        )

    winners = defaultdict(set)
    for lot_id, inn, win in bids:
        if win and lots[lot_id][0] >= args.cutoff:
            winners[lot_id].add(inn)
    rng = np.random.default_rng(args.seed)
    query_lots = sorted(winners)
    query_lots = rng.choice(query_lots, size=min(args.queries, len(query_lots)), replace=False)

    methods = ("okpd2", "vectors", "hybrid")
    hits = {m: defaultdict(lambda: np.zeros(len(KS) + 1)) for m in methods}
    counts = defaultdict(int)
    unseen = 0
    with pipeline.timed(f"[06] Ranking {len(query_lots)} queries"):
        for lot_id in query_lots.tolist():
            channel = lots[lot_id][1]
            truth = {col[inn] for inn in winners[lot_id] if inn in col}
            counts[channel] += 1
            counts["all"] += 1
            if not truth:
                unseen += 1
                continue

            keys = [prefix_row[p] for p in lot_prefixes.get(lot_id, ())]
            weights = np.array([OKPD2_LEVEL_WEIGHTS.get(len(prefixes[k]), 0.0) for k in keys])
            okpd2 = history.top_suppliers(
                history.score(by_okpd2, np.array(keys, dtype=int), weights), 100
            )

            query = emb.vectors[emb.lot_text_ids[lot_row[lot_id]]]
            rows, sims = similar_texts(emb.vectors, query, args.top_texts)
            vectors = history.top_suppliers(
                history.score(by_text, rows, np.clip(sims, 0, None)), 100
            )

            fused = history.reciprocal_rank_fusion([okpd2, vectors], len(inns))
            ranked = {
                "okpd2": okpd2,
                "vectors": vectors,
                "hybrid": history.top_suppliers(fused, 100),
            }
            for method, ranking in ranked.items():
                top = ranking[:20].tolist()
                rank = next((i + 1 for i, c in enumerate(top) if c in truth), None)
                row = np.array(
                    [rank is not None and rank <= k for k in KS] + [1 / rank if rank else 0]
                )
                for group in (channel, "all"):
                    hits[method][group] += row

    print(f"    winners never seen before the cutoff: {unseen} of {counts['all']} queries")
    header = "  ".join(f"R@{k:<3}" for k in KS) + "  MRR@20"
    for group in ["all", *sorted(g for g in counts if g != "all")]:
        print(f"\n    {group} ({counts[group]} queries)\n    {'method':8}  {header}")
        for method in methods:
            values = hits[method][group] / counts[group]
            print(f"    {method:8}  " + "  ".join(f"{v:.3f}" for v in values))


if __name__ == "__main__":
    main()
