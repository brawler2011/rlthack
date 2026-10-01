from typing import Optional, Literal
from pydantic import BaseModel
from app.schemas.lot import LotBase
from app.schemas.xai import XaiReport

RoleType = Literal["MANUFACTURER", "DISTRIBUTOR", "SUPPLIER"]

class SupplierProfile(BaseModel):
    inn: str
    kpp: str
    name: Optional[str] = None
    role: RoleType
    role_display: str
    score: float
    win_rate: float
    contracts_count: int
    avg_contract_price: float
    is_spb_lo: bool
    is_smp: bool
    xai: Optional[XaiReport] = None

class SupplierSearchRequest(BaseModel):
    lot: LotBase
    role_filter: Optional[list[RoleType]] = None
    only_spb_lo: bool = False
    only_smp: bool = False
    min_win_rate: Optional[float] = None
    limit: int = 20

class SupplierSearchResponse(BaseModel):
    total: int
    items: list[SupplierProfile]
    inference_time_ms: float
