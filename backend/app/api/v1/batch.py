from datetime import date

from fastapi import APIRouter, Depends, Query

from app.core.database import get_db
from app.schemas.batch import BatchResponse
from app.services.batch_service import batch_service

router = APIRouter(prefix="/batch", tags=["Batch"])


@router.post("/simulate", response_model=BatchResponse, operation_id="simulate_batch")
def simulate_batch_recommendations(
    day: date | None = Query(default=None, description="Notices of this day; default: the last"),
    max_lots: int = Query(default=10, ge=1, le=50),
    per_lot: int = Query(default=5, ge=1, le=20, description="Known suppliers to invite"),
    new_per_lot: int = Query(default=2, ge=0, le=10, description="New registry companies"),
    conn=Depends(get_db),
):
    """The background robot for one day: newly published notices, suppliers to invite for each
    (known ones with the reason, plus new companies from the SME registry)."""
    return batch_service.run_daily_match(conn, day, max_lots, per_lot, new_per_lot)
