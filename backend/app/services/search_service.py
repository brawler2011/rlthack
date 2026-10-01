from app.schemas.supplier import SupplierSearchRequest, SupplierSearchResponse


class SearchService:
    """Orchestrator for the supplier matching pipeline."""

    def search(self, request: SupplierSearchRequest) -> SupplierSearchResponse:
        # Pipeline scaffold: candidate retrieval -> CatBoost scoring -> XAI
        return SupplierSearchResponse(total=0, items=[], inference_time_ms=0.0)


search_service = SearchService()
