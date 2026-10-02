from pydantic import Field

from app.schemas.base import ContractModel
from app.schemas.errors import ValidationIssue
from app.schemas.supplier import SearchResponse, SupplierCard


class CsvBatchResponse(ContractModel):
    lots: list[SearchResponse]
    supplier_cards: dict[str, SupplierCard | None]
    total_lots: int
    total_items: int
    total_recommendations: int
    timing_ms: float
    selection_policy: str = Field(description="Human-readable automatic selection rule")


class CsvBatchErrorResponse(ContractModel):
    detail: str | list[ValidationIssue]
