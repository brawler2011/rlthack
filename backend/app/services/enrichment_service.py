from fastapi import HTTPException

from app.schemas.supplier import ROLE_DISPLAY, CompanyTrust, OkpdExperience, SupplierCard
from app.schemas.xai import EvidenceLot
from app.services.trust import has_table, role_from_okved, trust_rows, warnings

CARD_SQL = """
SELECT coalesce(c.inn, p.inn) AS inn, c.name, c.role, c.role_reason, c.okved_main,
       c.okved_main_name, coalesce(c.okved_extra, '{}') AS okved_extra,
       coalesce(c.region_code, p.region_code) AS region_code, p.is_spb_lo, c.msp_category,
       c.headcount, c.msp_since, coalesce(p.n_bids, 0) AS n_bids, coalesce(p.n_wins, 0) AS n_wins,
       p.win_rate, p.avg_won_price::float8 AS avg_won_price,
       coalesce(p.n_customers, 0) AS n_customers
FROM (SELECT %(inn)s AS inn) q
LEFT JOIN companies c ON c.inn = q.inn
LEFT JOIN supplier_profile p ON p.inn = q.inn
WHERE c.inn IS NOT NULL OR p.inn IS NOT NULL
"""
OKPD2_SQL = """
SELECT prefix, n_bids, n_wins FROM supplier_okpd2
WHERE inn = %s AND level = 4 ORDER BY n_wins DESC, n_bids DESC LIMIT 5
"""
RECENT_SQL = """
SELECT l.lot_id, l.publish_date, l.subject, l.start_price::float8 AS start_price,
       b.is_winner AS won
FROM bids b JOIN lots l USING (lot_id)
WHERE b.supplier_inn = %s ORDER BY l.publish_date DESC, l.lot_id DESC LIMIT 5
"""


class EnrichmentService:
    """Company cards: history from the data plus the SME registry."""

    def supplier_card(self, conn, inn: str) -> SupplierCard:
        card = conn.execute(CARD_SQL, {"inn": inn}).fetchone()
        if card is None:
            raise HTTPException(404, f"Компания с ИНН {inn} не найдена")
        role = card.pop("role")
        org = trust_rows(conn, [inn]).get(inn) if has_table(conn) else None
        if org and role is None:  # outside the SME registry: name and OKVED from FNS
            card["name"] = card["name"] or org["name"]
            role, card["role_reason"] = role_from_okved(org["okved"], card["name"])
            card["okved_main"] = card["okved_main"] or org["okved"]
        role = role or "UNKNOWN"
        return SupplierCard(
            **{k: v for k, v in card.items() if k != "okved_main_name"},
            okved_name=card["okved_main_name"],
            role=role,
            role_display=ROLE_DISPLAY[role],
            top_okpd2=[OkpdExperience(**r) for r in conn.execute(OKPD2_SQL, (inn,)).fetchall()],
            recent_lots=[EvidenceLot(**r) for r in conn.execute(RECENT_SQL, (inn,)).fetchall()],
            trust=self._trust(org),
        )

    @staticmethod
    def _trust(org: dict | None) -> CompanyTrust | None:
        if not org:
            return None
        return CompanyTrust(
            **{k: org[k] for k in ("revenue", "expenses", "taxes_paid", "tax_debt", "headcount")},
            registered=org["registered"],
            status=org["status"],
            warnings=warnings(org, None),
        )


enrichment_service = EnrichmentService()
