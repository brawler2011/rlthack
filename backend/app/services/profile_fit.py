"""Explain lot fit through independent, auditable evidence; wins do not prove execution."""

from app.ml.expansion import Affinity
from app.ml.profile_rules import RULES, within
from app.schemas.supplier import ProfileEvidence, ProfileFit

LABELS = {
    "HISTORY": "Есть победы в закупках по профилю лота",
    "PRODUCT": "Заявлена продукция по профилю лота",
    "PROFILE": "Подходит по указанному ОКВЭД",
    "STATISTICAL": "Соответствие поддерживается историей рынка",
    "UNKNOWN": "Недостаточно данных для оценки соответствия",
}


def make_evidence(**values) -> ProfileEvidence:
    return ProfileEvidence(
        **{
            "okved_code": None,
            "source_url": None,
            "sample_size": None,
            "share": None,
            "lot_ids": [],
            **values,
        }
    )


def assess_profile(
    codes: list[str],
    company: dict,
    affinity: Affinity | None = None,
    history: list[dict] | None = None,
) -> ProfileFit:
    """Assess every distinct requested code; evidence never implies whole-lot capability."""
    codes = sorted(set(codes))
    activities = list(
        dict.fromkeys(
            [company.get("okved_main") or company.get("okved")]
            + list(company.get("okved_extra") or [])
        )
    )
    activities = [code for code in activities if code]
    evidence = []
    for code in codes:
        wins = [
            row
            for row in history or []
            if row.get("is_winner")
            and any(
                len(past) >= 5 and past[:5] == code[:5] for past in row.get("okpd2_codes") or []
            )
        ]
        if wins:
            evidence.append(
                make_evidence(
                    kind="HISTORY",
                    okpd2_code=code,
                    source="История закупок",
                    description=f"ОКПД2 {code}: {len(wins)} побед в закупках этой группы. "
                    "Исполнение контрактов в исходных данных не подтверждено.",
                    sample_size=len(wins),
                    lot_ids=[row["lot_id"] for row in wins[:3]],
                )
            )
        for product in company.get("products") or []:
            if len(product) >= 5 and (within(code, product) or within(product, code)):
                evidence.append(
                    make_evidence(
                        kind="PRODUCT",
                        okpd2_code=code,
                        source="Реестр МСП ФНС",
                        source_url="https://rmsp.nalog.ru/",
                        description=f"В реестре МСП компания заявляет выпуск продукции {product}. "
                        "Характеристики и наличие товара требуют проверки.",
                    )
                )
                break
        for prefix, allowed, category in RULES:
            if not within(code, prefix):
                continue
            for activity in activities:
                if any(within(activity, target) for target in allowed):
                    evidence.append(
                        make_evidence(
                            kind="REFERENCE",
                            okpd2_code=code,
                            okved_code=activity,
                            source="Правила соответствия категорий сервиса",
                            description=f"{category}: ОКВЭД {activity} подходит по справочнику "
                            "производства и поставки. Возможность конкретной поставки "
                            "требует проверки.",
                        )
                    )
                    break
        if affinity:
            table = affinity.for_codes([code])
            key = code[:5] if code[:5] in affinity.shares else code[:2]
            for activity in activities:
                share = table.get(activity[:5], 0)
                if share < 0.05:
                    continue
                total = affinity.totals.get(key)
                scope = "группы" if len(key) == 5 else "класса"
                sample = f"; выборка — {total} побед" if total is not None else ""
                evidence.append(
                    make_evidence(
                        kind="STATISTICS",
                        okpd2_code=code,
                        okved_code=activity,
                        source="История победителей закупок",
                        description=f"Компании с ОКВЭД {activity[:5]} получили {share:.0%} побед "
                        f"в закупках {scope} ОКПД2 {key}{sample}. "
                        "Это статистическая связь, а не опыт данной компании.",
                        sample_size=total,
                        share=share,
                    )
                )
                break
    kinds = {item.kind for item in evidence}
    status = next(
        (
            status
            for kind, status in (
                ("HISTORY", "HISTORY"),
                ("PRODUCT", "PRODUCT"),
                ("REFERENCE", "PROFILE"),
                ("STATISTICS", "STATISTICAL"),
            )
            if kind in kinds
        ),
        "UNKNOWN",
    )
    # Class fallback is too broad to assert coverage of a particular lot item.
    covered = {item.okpd2_code for item in evidence if item.kind != "STATISTICS"}
    return ProfileFit(
        status=status,
        label=LABELS[status],
        covered_codes=sorted(covered),
        missing_codes=[code for code in codes if code not in covered],
        evidence=evidence,
    )
