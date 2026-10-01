class BatchService:
    """Background worker for automated supplier matching against new procurement notices."""

    def run_daily_match(self, date_from: str = None) -> list[dict]:
        return []


batch_service = BatchService()
