from fastapi import APIRouter

from app.schemas.supplier import SupplierSearchRequest, SupplierSearchResponse
from app.services.search_service import search_service

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@router.post("/search", response_model=SupplierSearchResponse, operation_id="search_suppliers")
def search_suppliers(request: SupplierSearchRequest) -> SupplierSearchResponse:
    """Search and rank suppliers matching procurement parameters."""
    return search_service.search(request)
