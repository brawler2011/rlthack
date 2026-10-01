"""New suppliers outside the bidding history: registry companies whose activity fits the lot.

OKPD2 codes of goods rarely share digits with the OKVED of those who supply them (medicines are
won by wholesalers with OKVED 46.46), so the fit is learned from history: for each OKPD2 group,
the share of wins taken by companies of each main OKVED group. A registry company scores that
share for its main OKVED group, half of it for an additional one, plus a bonus when it declares
making a product with the lot's code. Size, region and age only break ties inside a group.

Licenses narrow a group for regulated goods: the share of wins taken by holders of a license
(pharmacy, medical, waste) is learned the same way and adds to the score of its holders.
"""

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

import numpy as np

EXTRA_OKVED_WEIGHT = 0.5
PRODUCT_BONUS = 1.0
LICENSE_WEIGHT = 0.5
MIN_WINS = 3  # OKPD2 keys with fewer wins fall back to the class level
MIN_LIFT = 3  # a license counts for a lot if its winners hold it this much more often than usual

WINS_SQL = """
SELECT array_agg(DISTINCT i.okpd2_code), c.okved_main
FROM bids b
JOIN lots l USING (lot_id)
JOIN lot_items i USING (lot_id)
JOIN companies c ON c.inn = b.supplier_inn
WHERE b.is_winner AND l.publish_date < %s AND i.okpd2_code IS NOT NULL
GROUP BY b.lot_id, c.okved_main
"""

LICENSE_WINS_SQL = """
SELECT array_agg(DISTINCT i.okpd2_code), c.licenses
FROM bids b
JOIN lots l USING (lot_id)
JOIN lot_items i USING (lot_id)
JOIN companies c ON c.inn = b.supplier_inn
WHERE b.is_winner AND l.publish_date < %s AND i.okpd2_code IS NOT NULL
GROUP BY b.lot_id, c.inn
"""

REGISTRY_SQL = """
SELECT inn, okved_main, okved_extra, products, region_code, msp_category, headcount,
       (msp_since - DATE '1970-01-01'), licenses
FROM companies ORDER BY inn
"""


@dataclass
class Affinity:
    shares: dict[str, dict[str, float]]  # OKPD2 group (XX.XX) or class (XX) -> label -> share

    def for_codes(self, okpd2_codes: list[str]) -> dict[str, float]:
        """Share of wins per label (OKVED group, license) for a lot: by OKPD2 group, else class."""
        result: dict[str, float] = {}
        for code in okpd2_codes:
            table = self.shares.get(code[:5]) or self.shares.get(code[:2]) or {}
            for group, share in table.items():
                result[group] = max(result.get(group, 0.0), share)
        return result


def affinity_from_db(conn, before: date = date.max) -> Affinity:
    """Learn the OKVED fit from wins of registry companies on lots published before a date."""
    return learn_affinity(conn.execute(WINS_SQL, (before,)).fetchall())


def license_affinity_from_db(conn, before: date = date.max) -> Affinity:
    """Learn the license fit from wins of registry companies on lots published before a date."""
    return learn_license_affinity(conn.execute(LICENSE_WINS_SQL, (before,)).fetchall())


def _shares(wins: Iterable[tuple[list[str], Iterable[str]]]) -> Affinity:
    """Share of the wins under each OKPD2 key that went to winners with each label."""
    counts: dict[str, Counter] = defaultdict(Counter)
    totals: Counter = Counter()
    for codes, labels in wins:
        for key in {c[:5] for c in codes} | {c[:2] for c in codes}:
            totals[key] += 1
            counts[key].update(labels)
    return Affinity(
        {
            key: {label: n / totals[key] for label, n in counts[key].items()}
            for key in totals
            if totals[key] >= MIN_WINS
        }
    )


def learn_affinity(wins: Iterable[tuple[list[str], str | None]]) -> Affinity:
    """wins: OKPD2 codes of a won lot and the winner's main OKVED."""
    return _shares((codes, [okved[:5]]) for codes, okved in wins if okved)


def learn_license_affinity(wins: Iterable[tuple[list[str], list[str]]]) -> Affinity:
    """wins: OKPD2 codes of a won lot and the winner's licenses (winners without any count too).

    Only licenses that winners of the key hold more often than winners overall are kept.
    """
    wins = list(wins)
    overall = _shares((["00"], licenses) for _, licenses in wins).shares.get("00", {})
    fit = _shares(wins)
    return Affinity(
        {
            key: {lic: s for lic, s in table.items() if s >= MIN_LIFT * overall[lic]}
            for key, table in fit.shares.items()
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
    by_license: dict[str, np.ndarray]


def load_registry(conn) -> Registry:
    rows = conn.execute(REGISTRY_SQL).fetchall()
    by_main, by_extra, by_product = defaultdict(list), defaultdict(list), defaultdict(list)
    by_license = defaultdict(list)
    for i, (_, main, extra, products, *_, licenses) in enumerate(rows):
        if main:
            by_main[main[:5]].append(i)
        for group in {e[:5] for e in extra} - {(main or "")[:5]}:
            by_extra[group].append(i)
        for code in {p[:8] for p in products} | {p[:5] for p in products}:
            by_product[code].append(i)
        for license_ in licenses:
            by_license[license_].append(i)

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
        by_license=arrays(by_license),
    )


def expand(
    registry: Registry,
    affinity: Affinity,
    okpd2_codes: list[str],
    exclude: np.ndarray,
    day: int,
    top: int | None = 100,
    licenses: Affinity | None = None,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Top registry companies for a lot: rows, scores and a reason for each.

    exclude: boolean mask of companies to skip (already known suppliers);
    day: the lot date, companies that entered the registry later are skipped;
    licenses: the license fit, its holders get LICENSE_WEIGHT times the share of wins.
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
    # One license per company: the one whose holders win the largest share of such lots.
    bonus = np.zeros(len(registry.inns))
    why_license = np.full(len(registry.inns), -1)
    fits = licenses.for_codes(okpd2_codes) if licenses else {}
    for license_, share in sorted(fits.items(), key=lambda kv: (-kv[1], kv[0])):
        if (rows := registry.by_license.get(license_)) is not None:
            rows = rows[bonus[rows] == 0]
            bonus[rows] = LICENSE_WEIGHT * share
            why_license[rows] = len(reasons)
            wins = f"её владельцы выигрывают {share:.0%} похожих лотов"
            reasons.append(f"лицензия «{license_}»: {wins}")
    score += bonus

    score[exclude | (registry.since_day > day)] = 0
    found = np.flatnonzero(score > 0)
    # Lexicographic: the score first, the prior only orders companies with equal scores.
    order = found[np.lexsort((-registry.prior[found], -score[found]))][:top]  # top=None: all
    texts = [
        "; ".join(reasons[i] for i in pair if i >= 0)
        for pair in zip(why[order].tolist(), why_license[order].tolist(), strict=True)
    ]
    return order, score[order], texts
