from datetime import date

from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.core.database import get_db
from app.schemas.batch import BatchResponse
from app.schemas.csv_batch import CsvBatchErrorResponse, CsvBatchResponse
from app.services.batch_service import batch_service
from app.services.csv_batch_service import MAX_FILE_BYTES, csv_batch_service

router = APIRouter(prefix="/batch", tags=["Batch"])


@router.post(
    "/csv",
    response_model=CsvBatchResponse,
    operation_id="match_csv_batch",
    responses={
        422: {"model": CsvBatchErrorResponse, "description": "Invalid CSV or missing upload"},
        413: {"model": CsvBatchErrorResponse, "description": "CSV file too large"},
        503: {"model": CsvBatchErrorResponse, "description": "Matching engine unavailable"},
    },
)
def match_csv_batch(
    notices: UploadFile = File(description="Raw notices CSV"),
    items: UploadFile = File(description="Raw product items CSV"),
    conn=Depends(get_db),
):
    """Validate two CSVs and return all recommendations and company details in one response."""
    return csv_batch_service.run(
        conn, notices.file.read(MAX_FILE_BYTES + 1), items.file.read(MAX_FILE_BYTES + 1)
    )


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
