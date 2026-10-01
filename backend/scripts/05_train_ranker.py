"""Script 05: Train the CatBoost ranker on lots between two dates.

Features of each training lot come only from bids before the start of its month, the way the API
builds them, so the model learns to rank suppliers for lots it has not seen.
"""

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from app.config import settings  # noqa: E402
from app.etl import pipeline  # noqa: E402
from app.ml import ranker  # noqa: E402
from app.ml.candidates import FEATURES, History, by_month, load_dataset, query_rows  # noqa: E402
from app.ml.semantic_retriever import LotEmbeddings  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2025, 7, 1))
    parser.add_argument("--until", type=date.fromisoformat, default=date(2025, 10, 1))
    parser.add_argument("--queries", type=int, default=4000)
    parser.add_argument("--iterations", type=int, default=1500)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main():
    args = parse_args()
    emb = LotEmbeddings.load(settings.embeddings_dir)
    with pipeline.connect() as conn, pipeline.timed("[05] Reading data"):
        data = load_dataset(conn, emb)

    rows = query_rows(data, args.start, args.until, args.queries, args.seed)
    features, labels, groups = [], [], []
    with pipeline.timed(f"[05] Building features for {len(rows)} lots"):
        for cutoff, month_rows in by_month(data, rows).items():
            hist = History(data, emb, cutoff)
            for row in month_rows.tolist():
                q = data.query(row, emb)
                r = hist.retrieve(q)
                hit = np.isin(r.candidates, hist.columns(data.winners(row)))
                if not hit.any():
                    continue  # no winner among the candidates: nothing to learn from
                features.append(hist.features(q, r))
                labels.append(hit.astype(float))
                groups.append(np.full(len(hit), row))
    print(f"    lots with the winner among candidates: {len(groups)} of {len(rows)}")

    with pipeline.timed("[05] Training CatBoostRanker"):
        model = ranker.train(
            np.vstack(features), np.concatenate(labels), np.concatenate(groups), args.iterations
        )
    settings.catboost_model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(settings.catboost_model_path))
    print(f"    saved to {settings.catboost_model_path}")

    values = model.get_feature_importance(type="PredictionValuesChange")
    importance = sorted(zip(values, FEATURES, strict=True), reverse=True)
    print("    top features: " + ", ".join(f"{name} {value:.1f}" for value, name in importance[:8]))


if __name__ == "__main__":
    main()
