from typing import Literal

from pydantic import BaseModel

from app.schemas.lot import LotBase
from app.schemas.xai import XaiReport

RoleType = Literal["MANUFACTURER", "DISTRIBUTOR", "SUPPLIER"]


class SupplierProfile(BaseModel):
    inn: str
    kpp: str
    name: str | None = None
    role: RoleType
    role_display: str
    score: float
    win_rate: float
    contracts_count: int
    avg_contract_price: float
    is_spb_lo: bool
    is_smp: bool
    xai: XaiReport | None = None


class SupplierSearchRequest(BaseModel):
    lot: LotBase
    role_filter: list[RoleType] | None = None
    only_spb_lo: bool = False
    only_smp: bool = False
    min_win_rate: float | None = None
    limit: int = 20


class SupplierSearchResponse(BaseModel):
    total: int
    items: list[SupplierProfile]
    inference_time_ms: float
