"""Reliability of a company from open FNS data (the organizations table, 09_organizations).

Current risks reduce the online recommendation score after the historical ranker runs.
Offline model evaluations do not use these later reports. Missing data are neutral.
"""

import re

from app.ml.explainer import money

TRUST_SQL = """
SELECT inn, name, okved, status, registered, revenue::float8 AS revenue,
       expenses::float8 AS expenses, taxes_paid::float8 AS taxes_paid,
       tax_debt::float8 AS tax_debt, headcount, tax_fines::float8 AS tax_fines,
       revenue_as_of, taxes_paid_as_of, tax_debt_as_of, headcount_as_of,
       tax_fines_as_of, refreshed_at
FROM organizations WHERE inn = ANY(%s)
"""
HAS_TABLE_SQL = "SELECT to_regclass('organizations') IS NOT NULL AS ok"
TAX_DEBT_MIN = 50_000  # smaller arrears are usually a late payment
PRICE_SHARE_WARN = 0.5  # the lot's price is at least half of the yearly revenue
LOSS_RATIO = 1.1  # expenses above the income by 10%: a loss, not a rounding of break-even
# Status codes of the accounting statements registry (bo.nalog.gov.ru)
STATUS_TEXT = {
    "INACTIVE": "Компания прекратила деятельность",
    "LIQUIDATION_STAGE": "Компания в процессе ликвидации",
    "BANKRUPTCY_STAGE": "Процедура банкротства",
    "REORGANIZATION_STAGE": "Компания в процессе реорганизации",
}
UNRELIABLE_STATUS = {"INACTIVE", "LIQUIDATION_STAGE", "BANKRUPTCY_STAGE"}


def has_table(conn) -> bool:
    return bool(conn.execute(HAS_TABLE_SQL).fetchone()["ok"])


def trust_rows(conn, inns: list[str]) -> dict[str, dict]:
    """Organizations rows by INN (the table must exist, see has_table)."""
    if not inns:
        return {}
    return {r["inn"]: r for r in conn.execute(TRUST_SQL, (inns,)).fetchall()}


def warnings(org: dict | None, price: float | None) -> list[str]:
    if not org:
        return []
    found = []
    if text := STATUS_TEXT.get(org.get("status") or ""):
        found.append(text)
    revenue, expenses = org.get("revenue"), org.get("expenses")
    if revenue is not None and price:
        if revenue <= 0:
            found.append("Нет выручки за последний год")
        elif price >= revenue:
            found.append(f"НМЦК {money(price)} больше годовой выручки ({money(revenue)})")
        elif price / revenue >= PRICE_SHARE_WARN:
            found.append(f"НМЦК — {price / revenue:.0%} годовой выручки ({money(revenue)})")
    if revenue and expenses is not None and expenses > LOSS_RATIO * revenue:
        found.append(
            f"Убыток за последний год: расходы {money(expenses)} при доходах {money(revenue)}"
        )
    if (debt := org.get("tax_debt")) and debt >= TAX_DEBT_MIN:
        found.append(f"Налоговая задолженность {money(debt)}")
    if (fines := org.get("tax_fines")) and fines > 0:
        found.append(f"Неуплаченные штрафы за налоговые правонарушения {money(fines)}")
    return found


def is_reliable(org: dict | None, price: float | None) -> bool:
    """No liquidation, no tax debt and a yearly revenue above the lot's price."""
    if not org:
        return True  # no data is not a red flag
    if org.get("status") in UNRELIABLE_STATUS:
        return False
    if (org.get("tax_debt") or 0) >= TAX_DEBT_MIN:
        return False
    if (org.get("tax_fines") or 0) >= TAX_DEBT_MIN:
        return False
    revenue = org.get("revenue")
    return not (revenue is not None and price and revenue < price)


def reliability_factor(org: dict | None, price: float | None) -> float:
    """Multiply relevance by explicit risk discounts; do not renormalize afterwards.

    These are policy weights, not learned probabilities. Independent risks compound,
    while the two revenue warnings are mutually exclusive. Unknown values are neutral.
    """
    if not org:
        return 1.0
    factor = {
        "INACTIVE": 0.1,
        "LIQUIDATION_STAGE": 0.1,
        "BANKRUPTCY_STAGE": 0.1,
        "REORGANIZATION_STAGE": 0.9,
    }.get(org.get("status"), 1.0)
    # The tax-offence fine can also occur in the debt total; do not penalize it twice.
    if max(org.get("tax_debt") or 0, org.get("tax_fines") or 0) >= TAX_DEBT_MIN:
        factor *= 0.75
    revenue, expenses = org.get("revenue"), org.get("expenses")
    if revenue is not None and price:
        if revenue <= 0 or price >= revenue:
            factor *= 0.5
        elif price / revenue >= PRICE_SHARE_WARN:
            factor *= 0.8
    if revenue and expenses is not None and expenses > LOSS_RATIO * revenue:
        factor *= 0.85
    return factor


# State and municipal institutions file budget reports, not to the statements registry.
_INSTITUTION = re.compile(
    r"^(СПБ |САНКТ-ПЕТЕРБУРГСКОЕ )?(ФГБУЗ|ФГБУ|ФГБОУ|ФГКУ|ФГАУ|ФГУП|ФБУЗ|ФБУ|ГБУЗ|ГБУ|ГБОУ|ГБДОУ"
    r"|ГБПОУ|ГКУ|ГАУ|ГУП|МБУ|МБОУ|МБДОУ|МКУ|МАУ|МАОУ|МУП)\b|УЧРЕЖДЕНИЕ"
)


def role_from_okved(okved: str | None, name: str | None = None) -> tuple[str, str | None]:
    """The SME registry rule (companies.sql) for companies outside it, by OKVED from statements."""
    if not okved:
        if name and _INSTITUTION.search(name.upper()):
            return "SUPPLIER", "Государственное или муниципальное учреждение (не субъект МСП)"
        return "UNKNOWN", None
    reason = f"ОКВЭД {okved} по бухгалтерской отчётности (не субъект МСП)"
    division = okved[:2]
    if division.isdigit() and 10 <= int(division) <= 33:
        return "MANUFACTURER", reason
    if division == "46":
        return "DISTRIBUTOR", reason
    return "SUPPLIER", reason
