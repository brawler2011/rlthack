from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.schemas.supplier import SupplierCard
from app.services.enrichment_service import enrichment_service

router = APIRouter(prefix="/enrichment", tags=["Enrichment"])


@router.get("/{inn}", response_model=SupplierCard, operation_id="get_enrichment")
def get_enrichment(inn: str, conn=Depends(get_db)):
    """Company card: bidding history from the data plus OKVED, role and size from the SME
    registry. Works for new companies that never bid too."""
    return enrichment_service.supplier_card(conn, inn)
