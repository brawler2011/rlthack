"""Script 06: Offline evaluation of supplier recommendations on a time split.

History = bids before the cutoff; queries = later lots with a known winner.
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
from app.ml import ranker  # noqa: E402
from app.ml.candidates import History, load_dataset, query_rows  # noqa: E402
from app.ml.semantic_retriever import LotEmbeddings  # noqa: E402

KS = (1, 5, 10, 20)


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
    with pipeline.timed(f"[06] Building history before {args.cutoff}"):
        hist = History(data, emb, args.cutoff)
    model = None
    if settings.catboost_model_path.exists():
        model = ranker.load(settings.catboost_model_path)

    methods = ["okpd2", "vectors", "customer", "hybrid"] + (["ranker"] if model else [])
    hits = {m: defaultdict(lambda: np.zeros(len(KS) + 1)) for m in methods}
    counts = defaultdict(int)
    unseen = 0
    rows = query_rows(data, args.cutoff, None, args.queries, args.seed)
    with pipeline.timed(f"[06] Ranking {len(rows)} queries"):
        for row in rows.tolist():
            q = data.query(row, emb)
            channel = data.channels[q.channel] if q.channel >= 0 else "(empty)"
            counts[channel] += 1
            counts["all"] += 1
            truth = set(hist.columns(data.winners(row)).tolist())
            if not truth:
                unseen += 1
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
                row_hits = [rank is not None and rank <= k for k in KS] + [1 / rank if rank else 0]
                for group in (channel, "all"):
                    hits[method][group] += np.array(row_hits)

    print(f"    winners never seen before the cutoff: {unseen} of {counts['all']} queries")
    header = "  ".join(f"R@{k:<3}" for k in KS) + "  MRR@20"
    for group in ["all", *sorted(g for g in counts if g != "all")]:
        print(f"\n    {group} ({counts[group]} queries)\n    {'method':8}  {header}")
        for method in methods:
            values = hits[method][group] / counts[group]
            print(f"    {method:8}  " + "  ".join(f"{v:.3f}" for v in values))


if __name__ == "__main__":
    main()
