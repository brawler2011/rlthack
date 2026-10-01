"""Explanations for recommended suppliers: SHAP contributions of the ranker, grouped into facts a
procurement specialist understands and worded with the actual values."""

from dataclasses import dataclass, field

import numpy as np

from app.ml.candidates import FEATURES
from app.schemas.xai import EvidenceLot, Explanation, XaiFactor

# Features that tell one story are shown as one factor with their summed contribution.
GROUPS = {
    "similar_lots": ("vec_score", "vec_rank"),
    "okpd2": ("okpd2_score", "okpd2_rank"),
    "customer": ("customer_score", "customer_rank"),
    "agreement": ("fused_score",),
    "volume": ("log_bids", "log_wins"),
    "win_rate": ("win_rate_smoothed", "log_contested_bids"),
    "recency": ("days_since_win", "log_recent_wins"),
    "price": ("price_gap", "abs_price_gap"),
    "channel": ("channel_share",),
    "smp": ("smp_share", "smp_lot_x_share"),
    "region": ("spb_share",),
    "customers": ("log_customers",),
}
_INDEX = {name: i for i, name in enumerate(FEATURES)}
MAX_FACTORS = 4
NEGATIVE_THRESHOLD = -0.1


@dataclass
class Facts:
    """Values behind one recommendation, for the factor texts."""

    similar_wins: int = 0
    similar_bids: int = 0
    customer_wins: int = 0
    customer_bids: int = 0
    okpd2_group: str | None = None
    wins: int = 0
    bids: int = 0
    contested_bids: int = 0
    win_rate: float | None = None
    days_since_win: float = float("nan")
    recent_wins: int = 0
    typical_check: float | None = None
    lot_price: float | None = None
    channel: str | None = None
    channel_share: float = float("nan")
    smp_share: float = 0.0
    spb: bool = False
    customers: int = 0
    evidence: list[EvidenceLot] = field(default_factory=list)


def plural(n: int, forms: tuple[str, str, str]) -> str:
    """1 победа, 2 победы, 5 побед."""
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} {forms[0]}"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} {forms[1]}"
    return f"{n} {forms[2]}"


WINS = ("победа", "победы", "побед")
BIDS = ("участия", "участий", "участий")  # «из N участий»: genitive after «из»
CUSTOMERS = ("заказчиком", "заказчиками", "заказчиками")


def money(value: float) -> str:
    if value >= 1e6:
        return f"{value / 1e6:.1f} млн ₽".replace(".", ",")
    return f"{value / 1e3:.0f} тыс. ₽"


def describe(group: str, f: Facts) -> str | None:
    if group == "similar_lots":
        if not f.similar_bids:
            return "Похожих лотов в истории нет"
        return f"Похожие лоты: {plural(f.similar_wins, WINS)} из {plural(f.similar_bids, BIDS)}"
    if group == "okpd2":
        return f"Опыт по кодам ОКПД2 лота ({f.okpd2_group})" if f.okpd2_group else None
    if group == "customer":
        if not f.customer_bids:
            return "Не работал с этим заказчиком"
        wins, bids = plural(f.customer_wins, WINS), plural(f.customer_bids, BIDS)
        return f"{wins} у этого заказчика из {bids}"
    if group == "agreement":
        return "Найден сразу несколькими способами подбора"
    if group == "volume":
        return f"Всего {plural(f.wins, WINS)} из {plural(f.bids, BIDS)}"
    if group == "win_rate":
        if not f.contested_bids:
            return "Нет участий в конкурентных лотах"
        bids = plural(f.contested_bids, ("участие", "участия", "участий"))
        return f"Доля побед в конкурентных лотах {f.win_rate:.0%} ({bids})"
    if group == "recency":
        if np.isnan(f.days_since_win):
            return "Побед ещё не было"
        return (
            f"Последняя победа {int(f.days_since_win)} дн. назад, "
            f"{plural(f.recent_wins, WINS)} за последние 90 дней"
        )
    if group == "price":
        if not (f.typical_check and f.lot_price):
            return None
        return f"Типичный чек {money(f.typical_check)} при НМЦК {money(f.lot_price)}"
    if group == "channel":
        if not f.channel or np.isnan(f.channel_share):
            return None
        return f"{f.channel_share:.0%} участий в канале «{f.channel}»"
    if group == "smp":
        return f"{f.smp_share:.0%} участий — закупки только для СМП"
    if group == "region":
        return "Зарегистрирован в СПб / ЛО" if f.spb else "Зарегистрирован вне СПб / ЛО"
    if group == "customers":
        return f"Работал с {plural(f.customers, CUSTOMERS)}"
    return None


def explain(shap_row: np.ndarray, facts: Facts, relevance: float) -> Explanation:
    """Explanation from one row of SHAP values (one per feature) and the facts behind it."""
    impacts = {g: float(sum(shap_row[_INDEX[n]] for n in names)) for g, names in GROUPS.items()}
    ranked = sorted(impacts.items(), key=lambda kv: kv[1], reverse=True)
    chosen = [(g, v) for g, v in ranked if v > 0][:MAX_FACTORS]
    worst = ranked[-1]
    if worst[1] < NEGATIVE_THRESHOLD:
        chosen.append(worst)

    factors = [
        XaiFactor(name=g, impact=round(v, 3), text=text)
        for g, v in chosen
        if (text := describe(g, facts)) is not None
    ]
    positive = [f.text for f in factors if f.impact > 0][:2]
    level = "HIGH" if relevance >= 0.66 else "MEDIUM" if relevance >= 0.33 else "LOW"
    return Explanation(
        summary="; ".join(positive) or "Слабое совпадение с историей",
        level=level,
        factors=factors,
        evidence=facts.evidence,
    )
