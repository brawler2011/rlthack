from fastapi import APIRouter

from app.schemas.lot import LotCard, LotListItem
from app.services.search_service import search_service

router = APIRouter(prefix="/lots", tags=["Lots"])


@router.get("/search", response_model=list[LotListItem])
def search_lots(query: str = "", limit: int = 20):
    """Find lots by subject text, lot id or registry number."""
    return search_service.find_lots(query, limit)


@router.get("/{lot_id}", response_model=LotCard)
def get_lot(lot_id: int):
    """A lot with its items, OKPD2 codes and the real winners."""
    return search_service.lot_card(lot_id)
