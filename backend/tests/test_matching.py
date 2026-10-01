import numpy as np

from app.ml import history
from app.ml.semantic_retriever import similar_texts


def test_key_matrix_weights_wins_and_dampens_repeats():
    # key 0: supplier 0 won twice, supplier 1 bid once; key 1: supplier 1 won once
    matrix = history.key_matrix(
        keys=np.array([0, 0, 0, 1]),
        suppliers=np.array([0, 0, 1, 1]),
        wins=np.array([True, True, False, True]),
        n_keys=2,
        n_suppliers=2,
    )
    assert np.allclose(matrix.toarray(), np.log1p([[4.0, 1.0], [0.0, 2.0]]))


def test_score_and_top_suppliers():
    matrix = history.key_matrix(
        np.array([0, 1, 1]), np.array([0, 1, 2]), np.array([True, True, False]), 2, 3
    )
    scores = history.score(matrix, np.array([0, 1]), np.array([0.1, 1.0]))

    assert history.top_suppliers(scores, 2).tolist() == [1, 2]
    assert history.score(matrix, np.array([], dtype=int), np.array([])).tolist() == [0, 0, 0]


def test_reciprocal_rank_fusion_rewards_agreement():
    fused = history.reciprocal_rank_fusion([np.array([0, 1]), np.array([1, 2])], 3)
    assert history.top_suppliers(fused, 3).tolist()[0] == 1


def test_similar_texts():
    vectors = np.eye(3, dtype=np.float32)
    rows, sims = similar_texts(vectors, np.array([0.0, 1.0, 0.0], dtype=np.float32), 1)
    assert rows.tolist() == [1] and sims.tolist() == [1.0]
