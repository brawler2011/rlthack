"""New suppliers outside the bidding history: registry companies whose activity matches the lot.

A company matches through the lot's OKPD2 codes: products it declares in the SME registry
(strongest), its main OKVED group (XX.XX), an additional OKVED group, or its main OKVED class (XX).
OKPD2 and OKVED share the first digits for the same kind of goods and services.
"""

from collections import defaultdict
from dataclasses import dataclass

import numpy as np

MATCH_WEIGHTS = {"product": 4.0, "main_group": 3.0, "extra_group": 1.5, "main_class": 1.0}
REASONS = {
    "product": "заявляет выпуск продукции с кодом {code}",
    "main_group": "основной ОКВЭД в группе {code}",
    "extra_group": "дополнительный ОКВЭД в группе {code}",
    "main_class": "основной ОКВЭД в классе {code}",
}

REGISTRY_SQL = """
SELECT inn, okved_main, okved_extra, products, region_code, msp_category, headcount,
       (msp_since - DATE '1970-01-01')
FROM companies ORDER BY inn
"""


@dataclass
class Registry:
    inns: np.ndarray
    since_day: np.ndarray  # in the registry since, days since 1970-01-01
    prior: np.ndarray  # tie-breaker within a match level: size, region, age
    index: dict[tuple[str, str], np.ndarray]  # (match kind, code) -> company rows


def load_registry(conn) -> Registry:
    rows = conn.execute(REGISTRY_SQL).fetchall()
    index = defaultdict(list)
    for i, (_, main, extra, products, *_) in enumerate(rows):
        if main:
            index["main_group", main[:5]].append(i)
            index["main_class", main[:2]].append(i)
        for code in {e[:5] for e in extra}:
            index["extra_group", code].append(i)
        for code in {p[:8] for p in products} | {p[:5] for p in products}:
            index["product", code].append(i)

    category = np.array([r[5] or 0 for r in rows], dtype=float)
    headcount = np.array([r[6] or 0 for r in rows], dtype=float)
    spb = np.array([r[4] == "78" for r in rows], dtype=float)
    since = np.array([r[7] if r[7] is not None else 0 for r in rows], dtype=np.int64)
    years = (since.max() - since) / 365 if len(since) else since
    prior = (
        0.1 * category + 0.05 * np.log1p(headcount) / 7 + 0.1 * spb + 0.02 * np.minimum(years, 10)
    )
    return Registry(
        inns=np.array([r[0] for r in rows]),
        since_day=since,
        # Scaled below the smallest gap between match weights (0.5): it only orders companies
        # inside the same match level.
        prior=0.4 * prior / max(prior.max(initial=0.0), 1e-9),
        index={key: np.array(rows_, dtype=np.int64) for key, rows_ in index.items()},
    )


def expand(
    registry: Registry,
    okpd2_codes: list[str],
    exclude: np.ndarray,
    day: int,
    top: int | None = 100,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Top registry companies for a lot: rows, scores and a reason for each.

    exclude: boolean mask of companies to skip (already known suppliers);
    day: the lot date, companies that entered the registry later are skipped.
    """
    score = np.zeros(len(registry.inns))
    reason_kind: dict[int, tuple[float, str, str]] = {}
    for code in okpd2_codes:
        for kind, key in (
            ("product", code[:8]),
            ("product", code[:5]),
            ("main_group", code[:5]),
            ("extra_group", code[:5]),
            ("main_class", code[:2]),
        ):
            rows = registry.index.get((kind, key))
            if rows is None:
                continue
            weight = MATCH_WEIGHTS[kind] * (1.0 if len(key) > 5 or kind != "product" else 0.75)
            better = weight > score[rows]
            score[rows] = np.maximum(score[rows], weight)
            for r in rows[better].tolist():
                reason_kind[r] = (weight, kind, key)

    score[exclude | (registry.since_day > day)] = 0
    found = np.flatnonzero(score > 0)
    total = score[found] + registry.prior[found]
    order = found[np.argsort(-total, kind="stable")][:top]  # top=None keeps all
    reasons = [REASONS[reason_kind[r][1]].format(code=reason_kind[r][2]) for r in order.tolist()]
    return order, score[order] + registry.prior[order], reasons
