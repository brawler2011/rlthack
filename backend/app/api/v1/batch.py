from fastapi import APIRouter

from app.services.batch_service import batch_service

router = APIRouter(prefix="/batch", tags=["Batch"])


@router.post("/simulate")
def simulate_batch_recommendations():
    """Simulate background worker matching suppliers to new procurement notices."""
    return {"status": "ok", "matched_lots": batch_service.run_daily_match()}
