"""Example responses of the API contract: what the frontend can build against until the engine is
wired in. Values are realistic but made up."""

from datetime import date

from app.schemas.lot import LotCard, LotListItem
from app.schemas.supplier import (
    ROLE_DISPLAY,
    NewSupplier,
    OkpdExperience,
    SearchResponse,
    SupplierCard,
    SupplierRecommendation,
)
from app.schemas.xai import EvidenceLot, Explanation, XaiFactor

LOT = LotCard(
    lot_id=4760045,
    publish_date=date(2025, 10, 14),
    subject="Заправка картриджей для нужд СПб ГБУЗ «Городская поликлиника № 93»",
    procedure_name="Заправка картриджей",
    start_price=186_400.0,
    okpd2_codes=["95.11.10.130"],
    items=["Заправка картриджей"],
    customer_inn="7816047390",
    channel="ЭМ",
    is_smp=True,
    actual_winners=["7802587594"],
)

EVIDENCE = [
    EvidenceLot(
        lot_id=4512230,
        publish_date=date(2025, 6, 3),
        subject="Заправка и восстановление картриджей",
        start_price=150_000.0,
        won=True,
    ),
    EvidenceLot(
        lot_id=4388107,
        publish_date=date(2025, 3, 21),
        subject="Оказание услуг по заправке картриджей",
        start_price=92_500.0,
        won=False,
    ),
]

RECOMMENDATION = SupplierRecommendation(
    rank=1,
    inn="7802587594",
    name="ООО «ТОНЕР-СЕРВИС»",
    role="SUPPLIER",
    role_display=ROLE_DISPLAY["SUPPLIER"],
    role_reason="Основной ОКВЭД 95.11 «Ремонт компьютеров и периферийного оборудования»",
    score=0.94,
    win_rate=0.41,
    n_bids=87,
    n_wins=36,
    avg_won_price=171_300.0,
    region_code="78",
    is_spb_lo=True,
    is_smp=True,
    is_actual_winner=True,
    explanation=Explanation(
        summary="Выигрывал похожие лоты и уже работал с этим заказчиком",
        level="HIGH",
        factors=[
            XaiFactor(name="vec_score", impact=1.31, text="Выиграл 6 похожих лотов"),
            XaiFactor(name="customer_score", impact=0.84, text="3 победы у этого заказчика"),
            XaiFactor(
                name="abs_price_gap",
                impact=0.22,
                text="Средний чек 171 тыс. ₽ близок к НМЦК 186 тыс. ₽",
            ),
            XaiFactor(name="days_since_win", impact=0.18, text="Последняя победа 12 дней назад"),
        ],
        evidence=EVIDENCE,
    ),
)

NEW_SUPPLIER = NewSupplier(
    inn="7804123456",
    name="ООО «КАРТРИДЖ-ПРО»",
    role="SUPPLIER",
    role_display=ROLE_DISPLAY["SUPPLIER"],
    okved_main="95.11",
    okved_name="Ремонт компьютеров и периферийного компьютерного оборудования",
    region_code="78",
    msp_category=1,
    headcount=8,
    reason="основной ОКВЭД 95.11: такие компании выигрывают 64% похожих лотов",
    score=0.64,
)


def search_response() -> SearchResponse:
    return SearchResponse(
        lot=LOT,
        items=[RECOMMENDATION],
        new_suppliers=[NEW_SUPPLIER],
        total_candidates=100,
        timing_ms=180.0,
    )


def lot_list() -> list[LotListItem]:
    return [LotListItem(**LOT.model_dump(include=set(LotListItem.model_fields)))]


def supplier_card(inn: str) -> SupplierCard:
    return SupplierCard(
        inn=inn,
        name=RECOMMENDATION.name,
        role="SUPPLIER",
        role_display=ROLE_DISPLAY["SUPPLIER"],
        role_reason=RECOMMENDATION.role_reason,
        okved_main="95.11",
        okved_name=NEW_SUPPLIER.okved_name,
        okved_extra=["33.12", "47.41"],
        region_code="78",
        is_spb_lo=True,
        msp_category=1,
        headcount=14,
        msp_since=date(2016, 8, 1),
        n_bids=87,
        n_wins=36,
        win_rate=0.41,
        avg_won_price=171_300.0,
        n_customers=22,
        top_okpd2=[OkpdExperience(prefix="95.11", n_bids=61, n_wins=29)],
        recent_lots=EVIDENCE,
    )
