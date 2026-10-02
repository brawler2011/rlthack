from app.schemas.batch import MatchedLot


class BatchService:
    """Background worker for automated supplier matching against new procurement notices."""

    def run_daily_match(self, date_from: str | None = None) -> list[MatchedLot]:
        return []


batch_service = BatchService()
