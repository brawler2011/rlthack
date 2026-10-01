from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class XaiFactor(BaseModel):
    name: str = Field(description="Feature key, e.g. customer_score")
    impact: float = Field(description="Contribution to the rank score (SHAP); > 0 pushes up")
    text: str = Field(description="Human-readable reason with the actual value")


class EvidenceLot(BaseModel):
    """A past lot similar to the query that the supplier bid on."""

    lot_id: int
    publish_date: date | None = None
    subject: str | None = None
    start_price: float | None = None
    won: bool


class Explanation(BaseModel):
    summary: str
    level: Literal["HIGH", "MEDIUM", "LOW"]
    factors: list[XaiFactor]
    evidence: list[EvidenceLot] = []
