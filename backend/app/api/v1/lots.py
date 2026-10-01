from fastapi import APIRouter

from app.schemas.lot import LotResponse

router = APIRouter(prefix="/lots", tags=["Lots"])


@router.get("/search", response_model=list[LotResponse])
def search_lots(query: str = "", limit: int = 20):
    """Search historical lots and procurement notices for 2024-2025."""
    return []


@router.get("/{lot_id}", response_model=LotResponse)
def get_lot(lot_id: int):
    """Get detailed information for a specific lot."""
    return LotResponse(
        procedure_name="Sample Procurement Procedure",
        subject="Sample procurement subject",
        start_price=100000.0,
        okpd2_code="26.20",
        is_smp=True,
    )
