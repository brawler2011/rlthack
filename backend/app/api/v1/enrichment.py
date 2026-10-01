from fastapi import APIRouter

from app.services.enrichment_service import enrichment_service

router = APIRouter(prefix="/enrichment", tags=["Enrichment"])


@router.get("/{inn}")
def get_enrichment(inn: str):
    """Detailed company profile: OKVED, Minpromtorg registries, SME (MSP) status."""
    return enrichment_service.get_supplier_enrichment(inn)
