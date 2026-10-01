from app.schemas.lot import LotCard, LotListItem
from app.schemas.supplier import SearchRequest, SearchResponse
from app.services import examples


class SearchService:
    """Supplier matching for a lot. Returns contract examples until the engine is wired in."""

    def search(self, request: SearchRequest) -> SearchResponse:
        return examples.search_response()

    def find_lots(self, query: str, limit: int) -> list[LotListItem]:
        return examples.lot_list()[:limit]

    def lot_card(self, lot_id: int) -> LotCard:
        return examples.LOT


search_service = SearchService()
