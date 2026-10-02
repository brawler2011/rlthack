from app.schemas.enrichment import SupplierEnrichment


class EnrichmentService:
    """Data enrichment by INN: OKVED, counterparty roles, Minpromtorg (GISP) registry status."""

    def get_supplier_enrichment(self, inn: str) -> SupplierEnrichment:
        return SupplierEnrichment(
            inn=inn,
            role="SUPPLIER",
            is_gisp_manufacturer=False,
            okved_main=None,
            status="ACTIVE",
        )


enrichment_service = EnrichmentService()
