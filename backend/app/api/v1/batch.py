from fastapi import APIRouter

from app.schemas.batch import BatchResponse
from app.services.batch_service import batch_service

router = APIRouter(prefix="/batch", tags=["Batch"])


@router.post("/simulate", response_model=BatchResponse, operation_id="simulate_batch")
def simulate_batch_recommendations() -> BatchResponse:
    """Simulate background worker matching suppliers to new procurement notices."""
    return BatchResponse(status="ok", matched_lots=batch_service.run_daily_match())
