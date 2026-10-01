from fastapi import APIRouter

from app.services.enrichment_service import enrichment_service

router = APIRouter(prefix="/enrichment", tags=["Enrichment"])


@router.get("/{inn}")
def get_enrichment(inn: str):
    """Детальное досье компании: ОКВЭД, реестры Минпромторга, статус МСП."""
    return enrichment_service.get_supplier_enrichment(inn)
