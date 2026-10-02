from datetime import date
from typing import Literal

from pydantic import Field

from app.schemas.base import ContractModel


class XaiFactor(ContractModel):
    name: str = Field(description="Feature key, e.g. customer_score")
    impact: float = Field(description="Contribution to the rank score (SHAP); > 0 pushes up")
    text: str = Field(description="Human-readable reason with the actual value")


class EvidenceLot(ContractModel):
    """A past lot similar to the query that the supplier bid on."""

    lot_id: int
    publish_date: date | None
    subject: str | None
    start_price: float | None
    won: bool


class Explanation(ContractModel):
    summary: str
    level: Literal["HIGH", "MEDIUM", "LOW"]
    factors: list[XaiFactor]
    evidence: list[EvidenceLot]
