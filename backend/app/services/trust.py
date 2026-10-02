"""Reliability of a company from open FNS data (the organizations table, 09_organizations).

Warnings a procurement specialist checks before inviting a supplier: liquidation, tax debt, a
loss, and a contract that is large next to the company's yearly revenue. They are shown next to
the recommendation and do not change the ranking: the data are from 2025-2026, later than the
lots the model learned on.
"""

from app.ml.explainer import money

TRUST_SQL = """
SELECT inn, name, okved, status, registered, revenue::float8 AS revenue,
       expenses::float8 AS expenses, taxes_paid::float8 AS taxes_paid,
       tax_debt::float8 AS tax_debt, headcount
FROM organizations WHERE inn = ANY(%s)
"""
HAS_TABLE_SQL = "SELECT to_regclass('organizations') IS NOT NULL AS ok"
TAX_DEBT_MIN = 50_000  # smaller arrears are usually a late payment
PRICE_SHARE_WARN = 0.5  # the lot's price is at least half of the yearly revenue
STATUS_TEXT = {
    "LIQUIDATED": "Компания ликвидирована",
    "LIQUIDATING": "Компания в процессе ликвидации",
    "BANKRUPT": "Процедура банкротства",
}


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
    status = (org.get("status") or "").upper()
    if text := next((t for code, t in STATUS_TEXT.items() if code in status), None):
        found.append(text)
    revenue, expenses = org.get("revenue"), org.get("expenses")
    if revenue is not None and price:
        if revenue <= 0:
            found.append("Нет выручки за последний год")
        elif price >= revenue:
            found.append(f"НМЦК {money(price)} больше годовой выручки ({money(revenue)})")
        elif price / revenue >= PRICE_SHARE_WARN:
            found.append(f"НМЦК — {price / revenue:.0%} годовой выручки ({money(revenue)})")
    if revenue and expenses is not None and expenses > revenue:
        found.append(
            f"Убыток за последний год: расходы {money(expenses)} при доходах {money(revenue)}"
        )
    if (debt := org.get("tax_debt")) and debt >= TAX_DEBT_MIN:
        found.append(f"Налоговая задолженность {money(debt)}")
    return found


def is_reliable(org: dict | None, price: float | None) -> bool:
    """No liquidation, no tax debt and a yearly revenue above the lot's price."""
    if not org:
        return True  # no data is not a red flag
    status = (org.get("status") or "").upper()
    if any(code in status for code in STATUS_TEXT):
        return False
    if (org.get("tax_debt") or 0) >= TAX_DEBT_MIN:
        return False
    revenue = org.get("revenue")
    return not (revenue is not None and price and revenue < price)


def role_from_okved(okved: str | None) -> tuple[str, str | None]:
    """The SME registry rule (companies.sql) for companies outside it, by OKVED from statements."""
    if not okved:
        return "UNKNOWN", None
    reason = f"ОКВЭД {okved} по бухгалтерской отчётности (не субъект МСП)"
    division = okved[:2]
    if division.isdigit() and 10 <= int(division) <= 33:
        return "MANUFACTURER", reason
    if division == "46":
        return "DISTRIBUTOR", reason
    return "SUPPLIER", reason
