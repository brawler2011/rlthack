from typing import Literal

from pydantic import Field

from app.schemas.base import ContractModel
from app.schemas.lot import LotBase
from app.schemas.xai import XaiReport

RoleType = Literal["MANUFACTURER", "DISTRIBUTOR", "SUPPLIER"]


class SupplierProfile(ContractModel):
    inn: str
    kpp: str | None
    name: str | None
    role: RoleType
    role_display: str
    score: float
    win_rate: float
    contracts_count: int
    avg_contract_price: float
    is_spb_lo: bool
    is_smp: bool
    xai: XaiReport | None


class SupplierSearchRequest(ContractModel):
    lot: LotBase
    role_filter: list[RoleType] = Field(description="Empty list matches all roles.")
    only_spb_lo: bool
    only_smp: bool
    min_win_rate: float = Field(ge=0, le=1, description="Zero disables the win-rate filter.")
    limit: int = Field(gt=0)


class SupplierSearchResponse(ContractModel):
    total: int
    items: list[SupplierProfile]
    inference_time_ms: float
