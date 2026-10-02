from typing import Annotated

from fastapi import APIRouter, Query

from app.schemas.lot import LotResponse

router = APIRouter(prefix="/lots", tags=["Lots"])


@router.get("/search", response_model=list[LotResponse], operation_id="search_lots")
def search_lots(query: str = "", limit: Annotated[int, Query(gt=0)] = 20) -> list[LotResponse]:
    """Search historical lots and procurement notices for 2024-2025."""
    return []


@router.get("/{lot_id}", response_model=LotResponse, operation_id="get_lot")
def get_lot(lot_id: int) -> LotResponse:
    """Get detailed information for a specific lot."""
    return LotResponse(
        procedure_name="Sample Procurement Procedure",
        subject="Sample procurement subject",
        start_price=100000.0,
        okpd2_code="26.20",
        is_smp=True,
        customer_inn=None,
        customer_kpp=None,
        lot_id=lot_id,
        publish_date=None,
        procedure_id=None,
    )
