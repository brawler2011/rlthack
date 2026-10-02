from fastapi import APIRouter, Depends, Query

from app.core.database import get_db
from app.schemas.lot import LotCard, LotListItem
from app.services.search_service import search_service

router = APIRouter(prefix="/lots", tags=["Lots"])


@router.get("/search", response_model=list[LotListItem], operation_id="search_lots")
def search_lots(query: str = "", limit: int = Query(default=20, ge=1), conn=Depends(get_db)):
    """Find lots by subject text, lot id or registry number; newest first."""
    return search_service.find_lots(conn, query, limit)


@router.get("/{lot_id}", response_model=LotCard, operation_id="get_lot")
def get_lot(lot_id: int, conn=Depends(get_db)):
    """A lot with its items, OKPD2 codes and the real winners."""
    return search_service.lot_card(conn, lot_id)
