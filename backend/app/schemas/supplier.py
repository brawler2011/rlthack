from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.lot import LotCard, NewLot
from app.schemas.xai import EvidenceLot, Explanation

RoleType = Literal["MANUFACTURER", "DISTRIBUTOR", "SUPPLIER", "UNKNOWN"]
ROLE_DISPLAY = {
    "MANUFACTURER": "Производитель",
    "DISTRIBUTOR": "Дистрибьютор",
    "SUPPLIER": "Поставщик",
    "UNKNOWN": "Роль не определена",
}


class SearchFilters(BaseModel):
    roles: list[RoleType] | None = None
    only_spb_lo: bool = False
    only_smp: bool = False
    min_win_rate: float | None = Field(default=None, ge=0, le=1)


class SearchRequest(BaseModel):
    """Either an existing lot (lot_id) or a new one (lot)."""

    lot_id: int | None = None
    lot: NewLot | None = None
    filters: SearchFilters = SearchFilters()
    limit: int = Field(default=20, ge=1, le=100)
    new_limit: int = Field(default=10, ge=0, le=50, description="New suppliers to suggest")

    @model_validator(mode="after")
    def one_lot(self):
        if (self.lot_id is None) == (self.lot is None):
            raise ValueError("Pass exactly one of lot_id and lot")
        return self


class SupplierRecommendation(BaseModel):
    rank: int
    inn: str
    name: str | None = None
    role: RoleType
    role_display: str
    role_reason: str | None = None
    score: float = Field(description="Relevance in [0, 1] within this result")
    win_rate: float | None = Field(default=None, description="Over contested lots; None if none")
    n_bids: int
    n_wins: int
    avg_won_price: float | None = None
    region_code: str | None = None
    is_spb_lo: bool
    is_smp: bool | None = Field(default=None, description="In the FNS SME registry")
    is_actual_winner: bool = Field(default=False, description="Won this lot in reality (demo)")
    explanation: Explanation


class NewSupplier(BaseModel):
    """A company from the SME registry with no bids in the data."""

    inn: str
    name: str | None = None
    role: RoleType
    role_display: str
    okved_main: str | None = None
    okved_name: str | None = None
    region_code: str | None = None
    msp_category: int | None = Field(default=None, description="1 micro, 2 small, 3 medium")
    headcount: int | None = None
    reason: str
    score: float


class SearchResponse(BaseModel):
    lot: LotCard
    items: list[SupplierRecommendation]
    new_suppliers: list[NewSupplier]
    total_candidates: int
    timing_ms: float


class OkpdExperience(BaseModel):
    prefix: str
    n_bids: int
    n_wins: int


class SupplierCard(BaseModel):
    """Everything known about a company: history from the data plus the SME registry."""

    inn: str
    name: str | None = None
    role: RoleType
    role_display: str
    role_reason: str | None = None
    okved_main: str | None = None
    okved_name: str | None = None
    okved_extra: list[str] = []
    region_code: str | None = None
    is_spb_lo: bool | None = None
    msp_category: int | None = None
    headcount: int | None = None
    msp_since: date | None = None
    n_bids: int = 0
    n_wins: int = 0
    win_rate: float | None = None
    avg_won_price: float | None = None
    n_customers: int = 0
    top_okpd2: list[OkpdExperience] = []
    recent_lots: list[EvidenceLot] = []
