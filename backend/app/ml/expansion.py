"""New suppliers outside the bidding history: registry companies whose activity fits the lot.

OKPD2 codes of goods rarely share digits with the OKVED of those who supply them (medicines are
won by wholesalers with OKVED 46.46), so the fit is learned from history: for each OKPD2 group,
the share of wins taken by companies of each main OKVED group. A registry company scores its
group's share per company still in the pool if the group meets the profile threshold (a big
group's share is spread over more companies), half of it for an additional OKVED, plus a bonus
when it declares making a product with the lot's code. Licenses narrow a group for regulated
goods: the share of wins taken by holders of a license (pharmacy, medical, waste) is learned
the same way and adds to the holders' score. Size, region and age only break ties.
"""

import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

import numpy as np

EXTRA_OKVED_WEIGHT = 0.5
PRODUCT_BONUS = 1.0
MIN_WINS = 3  # OKPD2 keys with fewer wins fall back to the class level
MIN_LIFT = 3  # a license counts for a lot if its winners hold it this much more often than usual
MIN_LICENSE_SHARE = 0.05  # and at least this share of the lot's winners holds it
# New companies come from Saint Petersburg and Leningrad Region. Companies of other regions are
# in the table only because they bid somewhere in the data: in an evaluation they would be
# future bidders, a leak; in production they are all known already.
LOCAL_REGIONS = ("78", "47")
# A narrow specialist is more likely to win than a company with dozens of OKVED codes: the score
# is multiplied by SPEC_BASE + (1 - SPEC_BASE) * the share of its OKVED groups that fit the lot.
# On the cold lots after 2025-10-01: 1.38% -> 1.52% of winners in the top 100, better at every K.
SPEC_BASE = 0.75
SPEC_MIN_SHARE = 0.05  # an OKVED group fits the lot if it takes at least this share of the wins

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

    Only licenses that winners of the key hold often and more often than winners overall are kept.
    """
    wins = list(wins)
    overall = _shares((["00"], licenses) for _, licenses in wins).shares.get("00", {})
    fit = _shares(wins)
    return Affinity(
        {
            key: {
                lic: s
                for lic, s in table.items()
                if s >= max(MIN_LICENSE_SHARE, MIN_LIFT * overall[lic])
            }
            for key, table in fit.shares.items()
        }
    )


_PARENS = re.compile(r"\s*\([^()]*\)")
_TAIL = re.compile(r",\s*(?:за исключением|осуществляем|лицензируем)")
_ROMAN = re.compile(r"\b(?:i{1,3}|iv|v)\b")


def short_license(name: str, limit: int = 130) -> str:
    """License name for people: without clarifications in brackets and «, за исключением…»."""
    while (text := _PARENS.sub("", name)) != name:
        name = text
    text = _TAIL.split(text)[0].strip()
    text = _ROMAN.sub(lambda m: m.group().upper(), text)
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(",") + "…"
    return text


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
    local: np.ndarray  # registered in LOCAL_REGIONS
    groups: np.ndarray  # number of OKVED groups, main and additional


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
        local=np.array([r[4] in LOCAL_REGIONS for r in rows]),
        groups=np.array([len({e[:5] for e in r[2]} | {(r[1] or "")[:5]} - {""}) for r in rows]),
    )


def expand(
    registry: Registry,
    affinity: Affinity,
    okpd2_codes: list[str],
    exclude: np.ndarray,
    day: int,
    top: int | None = 100,
    licenses: Affinity | None = None,
    explain: bool = True,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Top registry companies for a lot: rows, scores relative to the best and a reason for each.

    exclude: boolean mask of companies to skip (already known suppliers);
    day: the lot date, companies that entered the registry later are skipped;
    licenses: the license fit, its holders score the share of wins per holder;
    explain: False skips the reasons (an empty list), for evaluations over the whole pool.
    """
    alive = registry.local & ~exclude & (registry.since_day <= day)
    score = np.zeros(len(registry.inns))
    fitting = np.zeros(len(registry.inns))
    reasons: list[str] = []  # texts; why[row] points into it, built only for the shown companies
    why = np.full(len(registry.inns), -1)

    def offer(rows, value, text):
        better = rows[value > score[rows]]
        score[better] = value
        why[better] = len(reasons)
        reasons.append(text)

    def per_company(share, rows):
        """A share of the wins spread over the companies of the group still in the pool."""
        return share / max(int(alive[rows].sum()), 1)

    for group, share in affinity.for_codes(okpd2_codes).items():
        # Eligibility and specialization must use the same definition of a fitting group.
        if share < SPEC_MIN_SHARE:
            continue
        wins = f"такие компании выигрывают {share:.0%} похожих лотов"
        if (rows := registry.by_main.get(group)) is not None:
            offer(rows, per_company(share, rows), f"основной ОКВЭД {group}: {wins}")
            fitting[rows] += 1
        if (rows := registry.by_extra.get(group)) is not None:
            value = per_company(EXTRA_OKVED_WEIGHT * share, rows)
            offer(rows, value, f"дополнительный ОКВЭД {group}: {wins}")
            fitting[rows] += 1
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
    # One license per company: the one with the largest share of wins per holder.
    bonus = np.zeros(len(registry.inns))
    why_license = np.full(len(registry.inns), -1)
    fits = [
        (per_company(share, rows), license_, share, rows)
        for license_, share in (licenses.for_codes(okpd2_codes) if licenses else {}).items()
        if (rows := registry.by_license.get(license_)) is not None
    ]
    for value, license_, share, rows in sorted(fits, key=lambda f: (-f[0], f[1])):
        rows = rows[bonus[rows] == 0]
        bonus[rows] = value
        why_license[rows] = len(reasons)
        wins = f"её владельцы выигрывают {share:.0%} похожих лотов"
        reasons.append(f"лицензия «{short_license(license_)}»: {wins}")
    score += bonus
    score *= SPEC_BASE + (1 - SPEC_BASE) * fitting / np.maximum(registry.groups, 1)

    score[~alive] = 0
    found = np.flatnonzero(score > 0)
    # Lexicographic: the score first, the prior only orders companies with equal scores.
    order = found[np.lexsort((-registry.prior[found], -score[found]))][:top]  # top=None: all
    relative = score[order] / score[order[0]] if len(order) else score[order]
    if not explain:
        return order, relative, []
    texts = [
        "; ".join(reasons[i] for i in pair if i >= 0)
        for pair in zip(why[order].tolist(), why_license[order].tolist(), strict=True)
    ]
    for k, row in enumerate(order.tolist()):
        fit, total = int(fitting[row]), int(registry.groups[row])
        if not fit:
            # Product and license evidence can justify a recommendation without OKVED fit.
            texts[k] += "; соответствие ОКВЭД профилю лота не подтверждено"
        elif total > 1:  # with one matching OKVED group it says nothing new
            texts[k] += f"; {fit} из {total} групп ОКВЭД компании — по профилю лота"
    return order, relative, texts
