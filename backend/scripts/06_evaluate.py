"""Script 06: Offline evaluation of supplier recommendations on a time split.

Queries = lots after the cutoff with a known winner; for each, history = bids before the start
of its month, the way the API serves it.
Strict metrics: share of queries with the actual winner in the top K (Recall@K) and MRR@20.
Soft metrics: any actual bidder in the top K (Hit@K) and the share of bidders found in the
top 20. Only e-shop lots list losing bidders; AIS GZ keeps just the winner.
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
from app.ml import ranker  # noqa: E402
from app.ml.candidates import History, by_month, load_dataset, query_rows  # noqa: E402
from app.ml.semantic_retriever import LotEmbeddings  # noqa: E402

KS = (1, 5, 10, 20)
SOFT_KS = (1, 10, 20)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cutoff", type=date.fromisoformat, default=date(2025, 10, 1))
    parser.add_argument("--queries", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main():
    args = parse_args()
    emb = LotEmbeddings.load(settings.embeddings_dir)
    with pipeline.connect() as conn, pipeline.timed("[06] Reading data"):
        data = load_dataset(conn, emb)
    model = None
    if settings.catboost_model_path.exists():
        model = ranker.load(settings.catboost_model_path)

    methods = ["okpd2", "vectors", "customer", "hybrid"] + (["ranker"] if model else [])
    hits = {m: defaultdict(lambda: np.zeros(len(KS) + 1)) for m in methods}
    soft = {m: defaultdict(lambda: np.zeros(len(SOFT_KS) + 1)) for m in methods}
    counts = defaultdict(int)
    unseen = 0
    rows = query_rows(data, args.cutoff, None, args.queries, args.seed)
    with pipeline.timed(f"[06] Ranking {len(rows)} queries"):
        for cutoff, month_rows in by_month(data, rows).items():
            hist = History(data, emb, cutoff)
            for row in month_rows.tolist():
                q = data.query(row, emb)
                channel = data.channels[q.channel] if q.channel >= 0 else "(empty)"
                counts[channel] += 1
                counts["all"] += 1
                truth = set(hist.columns(data.winners(row)).tolist())
                all_bidders = data.bidders(row)
                bidders = set(hist.columns(all_bidders).tolist())
                unseen += not truth
                if not bidders:
                    continue

                r = hist.retrieve(q)
                ranked = {
                    "okpd2": r.rankings[1],
                    "vectors": r.rankings[0],
                    "customer": r.rankings[2],
                    "hybrid": r.candidates,
                }
                if model:
                    ranked["ranker"] = ranker.rerank(model, r.candidates, hist.features(q, r))
                for method, ranking in ranked.items():
                    top = ranking[:20].tolist()
                    rank = next((i + 1 for i, c in enumerate(top) if c in truth), None)
                    row_hits = [rank is not None and rank <= k for k in KS]
                    row_hits.append(1 / rank if rank else 0)
                    found = [c in bidders for c in top]
                    soft_hits = [any(found[:k]) for k in SOFT_KS] + [sum(found) / len(all_bidders)]
                    for group in (channel, "all"):
                        hits[method][group] += np.array(row_hits)
                        soft[method][group] += np.array(soft_hits)

    print(f"    winners never seen before the lot's month: {unseen} of {counts['all']} queries")
    header = "  ".join(f"R@{k:<3}" for k in KS) + "  MRR@20"
    header += "  |  " + "  ".join(f"Hit@{k:<2}" for k in SOFT_KS) + "  Bidders@20"
    for group in ["all", *sorted(g for g in counts if g != "all")]:
        print(f"\n    {group} ({counts[group]} queries)\n    {'method':8}  {header}")
        for method in methods:
            strict = "  ".join(f"{v:.3f}" for v in hits[method][group] / counts[group])
            loose = "  ".join(f"{v:.3f} " for v in soft[method][group] / counts[group])
            print(f"    {method:8}  {strict}  |  {loose}")


if __name__ == "__main__":
    main()
