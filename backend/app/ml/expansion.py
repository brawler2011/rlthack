"""New suppliers outside the bidding history: registry companies whose activity fits the lot.

OKPD2 codes of goods rarely share digits with the OKVED of those who supply them (medicines are
won by wholesalers with OKVED 46.46), so the fit is learned from history: for each OKPD2 group,
the share of wins taken by companies of each main OKVED group. A registry company scores that
share for its main OKVED group, half of it for an additional one, plus a bonus when it declares
making a product with the lot's code. Size, region and age only break ties inside a group.
"""

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

import numpy as np

EXTRA_OKVED_WEIGHT = 0.5
PRODUCT_BONUS = 1.0
MIN_WINS = 3  # OKPD2 keys with fewer wins fall back to the class level

WINS_SQL = """
SELECT array_agg(DISTINCT i.okpd2_code), c.okved_main
FROM bids b
JOIN lots l USING (lot_id)
JOIN lot_items i USING (lot_id)
JOIN companies c ON c.inn = b.supplier_inn
WHERE b.is_winner AND l.publish_date < %s AND i.okpd2_code IS NOT NULL
GROUP BY b.lot_id, c.okved_main
"""

REGISTRY_SQL = """
SELECT inn, okved_main, okved_extra, products, region_code, msp_category, headcount,
       (msp_since - DATE '1970-01-01')
FROM companies ORDER BY inn
"""


@dataclass
class OkvedAffinity:
    shares: dict[str, dict[str, float]]  # OKPD2 group (XX.XX) or class (XX) -> OKVED group -> share

    def for_codes(self, okpd2_codes: list[str]) -> dict[str, float]:
        """Share of wins per OKVED group for a lot: by OKPD2 group, else by class."""
        result: dict[str, float] = {}
        for code in okpd2_codes:
            table = self.shares.get(code[:5]) or self.shares.get(code[:2]) or {}
            for group, share in table.items():
                result[group] = max(result.get(group, 0.0), share)
        return result


def affinity_from_db(conn, before: date = date.max) -> OkvedAffinity:
    """Learn the OKVED fit from wins of registry companies on lots published before a date."""
    return learn_affinity(conn.execute(WINS_SQL, (before,)).fetchall())


def learn_affinity(wins: Iterable[tuple[list[str], str | None]]) -> OkvedAffinity:
    """wins: OKPD2 codes of a won lot and the winner's main OKVED."""
    counts: dict[str, Counter] = defaultdict(Counter)
    for codes, okved in wins:
        if okved:
            for key in {c[:5] for c in codes} | {c[:2] for c in codes}:
                counts[key][okved[:5]] += 1
    return OkvedAffinity(
        {
            key: {group: n / sum(c.values()) for group, n in c.items()}
            for key, c in counts.items()
            if sum(c.values()) >= MIN_WINS
        }
    )


@dataclass
class Registry:
    inns: np.ndarray
    main_group: np.ndarray  # main OKVED group per company, "" if unknown
    since_day: np.ndarray  # in the registry since, days since 1970-01-01
    prior: np.ndarray  # in [0, 1): orders companies with equal scores
    by_main: dict[str, np.ndarray]  # OKVED group -> rows
    by_extra: dict[str, np.ndarray]
    by_product: dict[str, np.ndarray]  # product code prefix (XX.XX or XX.XX.XX) -> rows


def load_registry(conn) -> Registry:
    rows = conn.execute(REGISTRY_SQL).fetchall()
    by_main, by_extra, by_product = defaultdict(list), defaultdict(list), defaultdict(list)
    for i, (_, main, extra, products, *_) in enumerate(rows):
        if main:
            by_main[main[:5]].append(i)
        for group in {e[:5] for e in extra} - {(main or "")[:5]}:
            by_extra[group].append(i)
        for code in {p[:8] for p in products} | {p[:5] for p in products}:
            by_product[code].append(i)

    category = np.array([r[5] or 0 for r in rows], dtype=float)
    headcount = np.array([r[6] or 0 for r in rows], dtype=float)
    spb = np.array([r[4] == "78" for r in rows], dtype=float)
    since = np.array([r[7] if r[7] is not None else 0 for r in rows], dtype=np.int64)
    years = np.minimum((since.max(initial=0) - since) / 365, 10)
    prior = 0.3 * category / 3 + 0.2 * np.log1p(headcount) / 7 + 0.3 * spb + 0.2 * years / 10

    def arrays(index):
        return {key: np.array(rows_, dtype=np.int64) for key, rows_ in index.items()}

    return Registry(
        inns=np.array([r[0] for r in rows]),
        main_group=np.array([(r[1] or "")[:5] for r in rows]),
        since_day=since,
        prior=np.clip(prior, 0, 0.999),
        by_main=arrays(by_main),
        by_extra=arrays(by_extra),
        by_product=arrays(by_product),
    )


def expand(
    registry: Registry,
    affinity: OkvedAffinity,
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
    reasons: list[str] = []  # texts; why[row] points into it, built only for the shown companies
    why = np.full(len(registry.inns), -1)

    def offer(rows, value, text):
        better = rows[value > score[rows]]
        score[better] = value
        why[better] = len(reasons)
        reasons.append(text)

    for group, share in affinity.for_codes(okpd2_codes).items():
        wins = f"такие компании выигрывают {share:.0%} похожих лотов"
        if (rows := registry.by_main.get(group)) is not None:
            offer(rows, share, f"основной ОКВЭД {group}: {wins}")
        if (rows := registry.by_extra.get(group)) is not None:
            offer(rows, EXTRA_OKVED_WEIGHT * share, f"дополнительный ОКВЭД {group}: {wins}")
    # One bonus per company; the reason names the most specific matching code.
    declared = np.zeros(len(registry.inns), dtype=bool)
    codes = {c[:8] for c in okpd2_codes} | {c[:5] for c in okpd2_codes}
    for code in sorted(codes, key=lambda c: (-len(c), c)):
        if (rows := registry.by_product.get(code)) is not None:
            rows = rows[~declared[rows]]
            declared[rows] = True
            why[rows] = len(reasons)
            reasons.append(f"заявляет выпуск продукции {code}")
    score[declared] += PRODUCT_BONUS

    score[exclude | (registry.since_day > day)] = 0
    found = np.flatnonzero(score > 0)
    # Lexicographic: the score first, the prior only orders companies with equal scores.
    order = found[np.lexsort((-registry.prior[found], -score[found]))][:top]  # top=None: all
    return order, score[order], [reasons[i] for i in why[order].tolist()]
