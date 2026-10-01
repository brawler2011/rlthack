"""Supplier scores from bidding history: who bid on and won past lots similar to the query.

Past lots are grouped by a key (an embedded lot text, an OKPD2 prefix). Each key keeps a sparse
row of supplier weights, so scoring a query is one sparse product over the keys it matched.
"""

import numpy as np
from scipy import sparse

WIN_WEIGHT = 2.0  # a win counts double compared to a plain bid


def key_matrix(
    keys: np.ndarray, suppliers: np.ndarray, wins: np.ndarray, n_keys: int, n_suppliers: int
) -> sparse.csr_matrix:
    """(keys x suppliers) matrix of log1p(summed bid weights).

    log1p keeps a key shared by thousands of identical lots from drowning out everything else.
    """
    weights = np.where(wins, WIN_WEIGHT, 1.0)
    matrix = sparse.coo_matrix((weights, (keys, suppliers)), shape=(n_keys, n_suppliers)).tocsr()
    matrix.data = np.log1p(matrix.data)
    return matrix


def score(matrix: sparse.csr_matrix, keys: np.ndarray, key_weights: np.ndarray) -> np.ndarray:
    """Supplier scores: the matched key rows summed with the given weights."""
    if len(keys) == 0:
        return np.zeros(matrix.shape[1])
    return np.asarray(matrix[keys].T @ key_weights).ravel()


def top_suppliers(scores: np.ndarray, k: int) -> np.ndarray:
    """Columns of the k best non-zero scores, best first."""
    nonzero = np.flatnonzero(scores > 0)
    if len(nonzero) > k:
        nonzero = nonzero[np.argpartition(-scores[nonzero], k)[:k]]
    return nonzero[np.argsort(-scores[nonzero], kind="stable")]


def reciprocal_rank_fusion(
    rankings: list[np.ndarray],
    n_suppliers: int,
    weights: list[float] | None = None,
    k: int = 60,
) -> np.ndarray:
    """Fuse ranked lists into one score: weighted sum of 1 / (k + rank) over the lists."""
    fused = np.zeros(n_suppliers)
    for ranking, weight in zip(rankings, weights or [1.0] * len(rankings), strict=True):
        fused[ranking] += weight / (k + np.arange(1, len(ranking) + 1))
    return fused
