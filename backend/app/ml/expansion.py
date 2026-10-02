"""New suppliers outside the bidding history: registry companies whose activity fits the lot.

OKPD2 codes of goods rarely share digits with the OKVED of those who supply them (medicines are
won by wholesalers with OKVED 46.46), so the fit is learned from history: for each OKPD2 group,
the share of wins taken by companies of each main OKVED group. A registry company scores its
group's share per company still in the pool (a big group's share is spread over more companies),
half of it for an additional OKVED, plus a bonus when it declares making a product with the
lot's code. Licenses narrow a group for regulated goods: the share of wins taken by holders of
a license (pharmacy, medical, waste) is learned the same way and adds to the holders' score.

The score is multiplied by how much more often companies of its profile (category, staff, years
in the registry, region) win their first lots: learned on the newcomers of the last quarter.
"""

import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

EXTRA_OKVED_WEIGHT = 0.5
PRODUCT_BONUS = 1.0
MIN_WINS = 3  # OKPD2 keys with fewer wins fall back to the class level
MIN_LIFT = 3  # a license counts for a lot if its winners hold it this much more often than usual
MIN_LICENSE_SHARE = 0.05  # and at least this share of the lot's winners holds it

NEWCOMER_DAYS = 91  # the profile weights are learned on first wins in this window
PROFILE_PSEUDO = 2000  # smoothing: each profile starts as this many average companies
MIN_PROFILE_LIFT = 1.5  # the reason names the profile from this weight
OLD_DAYS = 5 * 365
STAFF_BOUNDS = (1, 5, 20)  # staff buckets 0, 1-4, 5-19, 20+
SOLE_TRADER = 9  # their staff is not published
CATEGORIES = {1: "микропредприятие", 2: "малое предприятие", 3: "среднее предприятие"}
STAFF = {0: "без сотрудников", 1: "1–4 сотрудника", 2: "5–19 сотрудников", 3: "20+ сотрудников"}

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
       (msp_since - DATE '1970-01-01'), licenses, is_individual
FROM companies ORDER BY inn
"""

KNOWN_SQL = """
SELECT DISTINCT b.supplier_inn FROM bids b JOIN lots l USING (lot_id) WHERE l.publish_date < %s
"""

WINNERS_SQL = """
SELECT DISTINCT b.supplier_inn FROM bids b JOIN lots l USING (lot_id)
WHERE b.is_winner AND l.publish_date >= %s AND l.publish_date < %s
"""

NEXT_DAY_SQL = "SELECT max(publish_date) + 1 FROM lots"


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
    profile: np.ndarray  # category * 100 + staff bucket * 10 + in Saint Petersburg
    by_main: dict[str, np.ndarray]  # OKVED group -> rows
    by_extra: dict[str, np.ndarray]
    by_product: dict[str, np.ndarray]  # product code prefix (XX.XX or XX.XX.XX) -> rows
    by_license: dict[str, np.ndarray]

    def segments(self, day: int) -> np.ndarray:
        """Profile and whether the company had been in the registry for 5 years by the day."""
        return self.profile * 10 + (day - self.since_day > OLD_DAYS)

    def describe(self, row: int, day: int) -> str:
        category, staff = divmod(int(self.profile[row]) // 10, 10)
        parts = ["ИП"] if staff == SOLE_TRADER else [CATEGORIES.get(category), STAFF[staff]]
        if day - self.since_day[row] > OLD_DAYS:
            parts.append("5+ лет в реестре МСП")
        return ", ".join(p for p in parts if p)


def load_registry(conn) -> Registry:
    rows = conn.execute(REGISTRY_SQL).fetchall()
    by_main, by_extra, by_product = defaultdict(list), defaultdict(list), defaultdict(list)
    by_license = defaultdict(list)
    for i, (_, main, extra, products, *_, licenses, _individual) in enumerate(rows):
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
    individual = np.array([bool(r[9]) for r in rows])
    staff = np.where(individual, SOLE_TRADER, np.searchsorted(STAFF_BOUNDS, headcount, "right"))

    def arrays(index):
        return {key: np.array(rows_, dtype=np.int64) for key, rows_ in index.items()}

    return Registry(
        inns=np.array([r[0] for r in rows]),
        main_group=np.array([(r[1] or "")[:5] for r in rows]),
        since_day=since,
        prior=np.clip(prior, 0, 0.999),
        profile=category.astype(np.int64) * 100 + staff * 10 + spb.astype(np.int64),
        by_main=arrays(by_main),
        by_extra=arrays(by_extra),
        by_product=arrays(by_product),
        by_license=arrays(by_license),
    )


def learn_profile_lift(
    segment: np.ndarray, pool: np.ndarray, won: np.ndarray, pseudo: float = PROFILE_PSEUDO
) -> dict[int, float]:
    """How many times more often than average the pool companies of each segment won."""
    rate = won[pool].sum() / max(pool.sum(), 1)
    if rate == 0:
        return {}
    segments, inverse = np.unique(segment[pool], return_inverse=True)
    counts = np.bincount(inverse)
    wins = np.bincount(inverse, weights=won[pool].astype(float))
    lift = (wins + pseudo * rate) / (counts + pseudo) / rate
    return dict(zip(segments.tolist(), lift.tolist(), strict=True))


def profile_weights_from_db(conn, registry: Registry, before: date | None = None) -> np.ndarray:
    """Per company: how many times more often its profile wins first lots than average.

    Learned on the quarter before the date (default: after the last lot): winners who had not
    bid before the quarter, among the registry companies that had not bid either.
    """
    if before is None:
        before = conn.execute(NEXT_DAY_SQL).fetchone()[0]
    start = before - timedelta(days=NEWCOMER_DAYS)
    known = [r[0] for r in conn.execute(KNOWN_SQL, (start,)).fetchall()]
    winners = [r[0] for r in conn.execute(WINNERS_SQL, (start, before)).fetchall()]
    start_day, before_day = ((d - date(1970, 1, 1)).days for d in (start, before))
    pool = ~np.isin(registry.inns, known) & (registry.since_day <= start_day)
    won = np.isin(registry.inns, winners)
    lift = learn_profile_lift(registry.segments(start_day), pool, won)
    return np.array([lift.get(s, 1.0) for s in registry.segments(before_day).tolist()])


def expand(
    registry: Registry,
    affinity: Affinity,
    okpd2_codes: list[str],
    exclude: np.ndarray,
    day: int,
    top: int | None = 100,
    licenses: Affinity | None = None,
    weights: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Top registry companies for a lot: rows, scores relative to the best and a reason for each.

    exclude: boolean mask of companies to skip (already known suppliers);
    day: the lot date, companies that entered the registry later are skipped;
    licenses: the license fit, its holders score the share of wins per holder;
    weights: per company, how much more often its profile wins (profile_weights_from_db).
    """
    alive = ~exclude & (registry.since_day <= day)
    score = np.zeros(len(registry.inns))
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
        wins = f"такие компании выигрывают {share:.0%} похожих лотов"
        if (rows := registry.by_main.get(group)) is not None:
            offer(rows, per_company(share, rows), f"основной ОКВЭД {group}: {wins}")
        if (rows := registry.by_extra.get(group)) is not None:
            value = per_company(EXTRA_OKVED_WEIGHT * share, rows)
            offer(rows, value, f"дополнительный ОКВЭД {group}: {wins}")
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
    if weights is not None:
        score *= weights

    score[~alive] = 0
    found = np.flatnonzero(score > 0)
    # Lexicographic: the score first, the prior only orders companies with equal scores.
    order = found[np.lexsort((-registry.prior[found], -score[found]))][:top]  # top=None: all
    texts = [
        "; ".join(reasons[i] for i in pair if i >= 0)
        for pair in zip(why[order].tolist(), why_license[order].tolist(), strict=True)
    ]
    if weights is not None:
        for k, row in enumerate(order.tolist()):
            if weights[row] >= MIN_PROFILE_LIFT:
                times = f"{weights[row]:.1f}".replace(".", ",")
                texts[k] += (
                    f"; профиль «{registry.describe(row, day)}»: "
                    f"среди новых победителей в {times} раза чаще среднего"
                )
    best = score[order[0]] if len(order) else 1.0
    return order, score[order] / best, texts
