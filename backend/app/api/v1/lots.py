from fastapi import APIRouter
from app.schemas.lot import LotResponse

router = APIRouter(prefix="/lots", tags=["Lots"])

@router.get("/search", response_model=list[LotResponse])
def search_lots(query: str = "", limit: int = 20):
    """Поиск по историческим лотам и извещениям 2024-2025."""
    return []

@router.get("/{lot_id}", response_model=LotResponse)
def get_lot(lot_id: int):
    """Получение детальной информации по конкретному лоту."""
    return LotResponse(
        procedure_name="Пример закупки",
        subject="Пример предмета закупки",
        start_price=100000.0,
        okpd2_code="26.20",
        is_smp=True
    )
