from typing import Literal

from app.schemas.base import ContractModel


class XaiFactor(ContractModel):
    factor_name: str
    shap_value: float
    description: str


class XaiReport(ContractModel):
    summary: str
    factors: list[XaiFactor]
    recommendation_level: Literal["HIGH", "MEDIUM", "LOW"]
