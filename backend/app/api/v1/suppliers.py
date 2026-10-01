from fastapi import APIRouter
from app.schemas.supplier import SupplierSearchRequest, SupplierSearchResponse
from app.services.search_service import search_service

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])

@router.post("/search", response_model=SupplierSearchResponse)
def search_suppliers(request: SupplierSearchRequest):
    """Поиск и ранжирование поставщиков под параметры закупки."""
    return search_service.search(request)
