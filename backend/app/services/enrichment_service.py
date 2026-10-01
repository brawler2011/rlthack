from app.schemas.supplier import SupplierCard
from app.services import examples


class EnrichmentService:
    """Company cards. Returns contract examples until the engine is wired in."""

    def supplier_card(self, inn: str) -> SupplierCard:
        return examples.supplier_card(inn)


enrichment_service = EnrichmentService()
