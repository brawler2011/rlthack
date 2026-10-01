class EnrichmentService:
    """Обогащение данных по ИНН: ОКВЭД, роли, статус Минпромторга (ГИСП)."""

    def get_supplier_enrichment(self, inn: str) -> dict:
        return {
            "inn": inn,
            "role": "SUPPLIER",
            "is_gisp_manufacturer": False,
            "okved_main": None,
            "status": "ACTIVE",
        }


enrichment_service = EnrichmentService()
