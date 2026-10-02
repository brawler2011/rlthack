from datetime import date

from pydantic import Field

from app.schemas.base import ContractModel
from app.schemas.lot import LotListItem


class Invitation(ContractModel):
    """A supplier the robot would invite to the lot's procurement."""

    inn: str
    name: str | None
    role_display: str
    score: float
    reason: str
    is_new: bool = Field(description="From the SME registry, never bid before")


class BatchLotResult(ContractModel):
    lot: LotListItem
    invitations: list[Invitation]
    actual_winners: list[str] = Field(description="Who really won (demo)")
    winner_invited: bool = Field(description="The real winner is among the invitations (demo)")


class BatchResponse(ContractModel):
    day: date = Field(description="Publication date of the processed notices")
    lots: list[BatchLotResult]
    total_invitations: int
    timing_ms: float
