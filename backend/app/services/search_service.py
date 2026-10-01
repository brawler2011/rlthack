from app.schemas.supplier import SupplierSearchRequest, SupplierSearchResponse


class SearchService:
    """Оркестратор пайплайна подбора поставщиков."""

    def search(self, request: SupplierSearchRequest) -> SupplierSearchResponse:
        # Каркас: отбор кандидатов -> CatBoost скоринг -> XAI
        return SupplierSearchResponse(total=0, items=[], inference_time_ms=0.0)


search_service = SearchService()
