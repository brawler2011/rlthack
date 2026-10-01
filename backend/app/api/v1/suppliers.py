from fastapi import APIRouter

from app.schemas.supplier import SearchRequest, SearchResponse
from app.services.search_service import search_service

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@router.post("/search", response_model=SearchResponse)
def search_suppliers(request: SearchRequest):
    """Rank suppliers for a lot from the data (lot_id) or a new one (lot), with explanations,
    plus new companies from the SME registry that fit the lot."""
    return search_service.search(request)
