from typing import Literal

from app.schemas.base import ContractModel
from app.schemas.lot import LotResponse
from app.schemas.supplier import SupplierSearchResponse


class MatchedLot(ContractModel):
    lot: LotResponse
    recommendations: SupplierSearchResponse


class BatchResponse(ContractModel):
    status: Literal["ok"]
    matched_lots: list[MatchedLot]
