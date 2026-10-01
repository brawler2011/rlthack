"""CatBoost ranker that reorders retrieved candidates using the features from candidates.py."""

from pathlib import Path

import numpy as np

from app.ml.candidates import FEATURES


def train(features: np.ndarray, labels: np.ndarray, groups: np.ndarray, iterations: int = 600):
    from catboost import CatBoostRanker, Pool  # heavy import, only when needed

    model = CatBoostRanker(
        loss_function="YetiRank",
        iterations=iterations,
        learning_rate=0.1,
        depth=6,
        random_seed=42,
        verbose=100,
    )
    model.fit(Pool(features, labels, group_id=groups, feature_names=list(FEATURES)))
    return model


def load(path: Path):
    from catboost import CatBoostRanker

    model = CatBoostRanker()
    model.load_model(str(path))
    return model


def rerank(model, candidates: np.ndarray, features: np.ndarray) -> np.ndarray:
    """Candidates ordered by the model score, best first."""
    return candidates[np.argsort(-model.predict(features), kind="stable")]
