from fastapi import APIRouter

from app.schemas.enrichment import SupplierEnrichment
from app.services.enrichment_service import enrichment_service

router = APIRouter(prefix="/enrichment", tags=["Enrichment"])


@router.get("/{inn}", response_model=SupplierEnrichment, operation_id="get_enrichment")
def get_enrichment(inn: str) -> SupplierEnrichment:
    """Detailed company profile: OKVED, Minpromtorg registries, SME (MSP) status."""
    return enrichment_service.get_supplier_enrichment(inn)
