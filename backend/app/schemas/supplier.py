from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.base import ContractModel
from app.schemas.lot import LotCard, NewLot
from app.schemas.xai import EvidenceLot, Explanation

RoleType = Literal["MANUFACTURER", "DISTRIBUTOR", "SUPPLIER", "UNKNOWN"]
ROLE_DISPLAY = {
    "MANUFACTURER": "Производитель",
    "DISTRIBUTOR": "Дистрибьютор",
    "SUPPLIER": "Поставщик",
    "UNKNOWN": "Роль не определена",
}


class SearchFilters(ContractModel):
    roles: list[RoleType] = Field(description="Empty list matches all roles")
    only_spb_lo: bool
    only_smp: bool
    min_win_rate: float = Field(ge=0, le=1, description="Zero disables the win-rate filter")
    only_reliable: bool = Field(
        description="Skip companies that are liquidated, owe taxes or have a revenue below the "
        "lot's initial price (open FNS data)"
    )


class SearchRequest(ContractModel):
    """Either an existing lot (lot_id) or a new one (lot)."""

    lot_id: int | None = Field(gt=0)
    lot: NewLot | None
    filters: SearchFilters
    limit: int = Field(ge=1, le=100)
    new_limit: int = Field(ge=0, le=50, description="New suppliers to suggest")

    @model_validator(mode="after")
    def one_lot(self):
        if (self.lot_id is None) == (self.lot is None):
            raise ValueError("Pass exactly one of lot_id and lot")
        return self


class ProfileEvidence(ContractModel):
    kind: Literal["REFERENCE", "STATISTICS", "PRODUCT", "HISTORY"]
    description: str
    okpd2_code: str
    okved_code: str | None
    source: str
    source_url: str | None
    sample_size: int | None
    share: float | None
    lot_ids: list[int]


class ProfileFit(ContractModel):
    status: Literal["HISTORY", "PRODUCT", "PROFILE", "STATISTICAL", "UNKNOWN"]
    label: str
    covered_codes: list[str]
    missing_codes: list[str]
    evidence: list[ProfileEvidence]


class SupplierRecommendation(ContractModel):
    rank: int
    inn: str
    name: str | None
    role: RoleType
    role_display: str
    role_reason: str | None
    profile_fit: ProfileFit | None
    score: float = Field(description="Relative relevance multiplied by the current FNS risk factor")
    base_score: float = Field(description="Relative relevance before the FNS risk adjustment")
    reliability_factor: float = Field(
        ge=0, le=1, description="FNS risk multiplier; 1 without risks"
    )
    win_rate: float | None = Field(description="Over contested lots; None if none")
    n_bids: int
    n_wins: int
    avg_won_price: float | None
    region_code: str | None
    is_spb_lo: bool
    is_smp: bool | None = Field(description="In the FNS SME registry")
    is_actual_winner: bool = Field(description="Won this lot in reality (demo)")
    explanation: Explanation
    warnings: list[str] = Field(
        description="Reliability warnings: tax debt, loss, revenue vs. the lot price"
    )


class NewSupplier(ContractModel):
    """A company from the SME registry with no bids in the data."""

    inn: str
    name: str | None
    role: RoleType
    role_display: str
    okved_main: str | None
    okved_name: str | None
    region_code: str | None
    msp_category: int | None = Field(description="1 micro, 2 small, 3 medium")
    headcount: int | None
    profile_fit: ProfileFit | None
    reason: str
    score: float
    base_score: float
    reliability_factor: float = Field(
        ge=0, le=1, description="FNS risk multiplier; 1 without risks"
    )
    warnings: list[str]


class SearchResponse(ContractModel):
    lot: LotCard
    items: list[SupplierRecommendation]
    new_suppliers: list[NewSupplier]
    total_candidates: int
    timing_ms: float


class OkpdExperience(ContractModel):
    prefix: str
    n_bids: int
    n_wins: int


class CompanyTrust(ContractModel):
    """Open FNS data: accounting statements, taxes, EGRUL."""

    revenue: float | None = Field(description="Income for the last year, RUB")
    expenses: float | None = Field(description="Expenses for the last year, RUB")
    taxes_paid: float | None = Field(description="Taxes and contributions paid, RUB")
    tax_debt: float | None = Field(description="Tax arrears, penalties and fines, RUB")
    headcount: int | None
    registered: date | None
    status: str | None = Field(
        description="ACTIVE, INACTIVE, LIQUIDATION_STAGE, ... from the statements registry"
    )
    warnings: list[str]
    tax_fines: float | None
    revenue_as_of: date | None
    taxes_paid_as_of: date | None
    tax_debt_as_of: date | None
    headcount_as_of: date | None
    tax_fines_as_of: date | None
    refreshed_at: date | None


class SupplierCard(ContractModel):
    """Everything known about a company: history from the data plus the SME registry."""

    inn: str
    name: str | None
    role: RoleType
    role_display: str
    role_reason: str | None
    okved_main: str | None
    okved_name: str | None
    okved_extra: list[str]
    region_code: str | None
    is_spb_lo: bool | None
    msp_category: int | None
    headcount: int | None
    msp_since: date | None
    n_bids: int
    n_wins: int
    win_rate: float | None
    avg_won_price: float | None
    n_customers: int
    top_okpd2: list[OkpdExperience]
    recent_lots: list[EvidenceLot]
    trust: CompanyTrust | None = Field(description="None without open FNS data")
