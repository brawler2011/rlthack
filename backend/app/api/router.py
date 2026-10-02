from fastapi import APIRouter

from app.api.v1 import batch, enrichment, lots, suppliers
from app.schemas.errors import ValidationErrorResponse
from app.schemas.health import HealthResponse

api_router = APIRouter(
    prefix="/api/v1",
    responses={422: {"model": ValidationErrorResponse, "description": "Validation Error"}},
)

api_router.include_router(suppliers.router)
api_router.include_router(lots.router)
api_router.include_router(enrichment.router)
api_router.include_router(batch.router)


@api_router.get("/health", tags=["Health"], response_model=HealthResponse, operation_id="health")
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service="rlthack-recsys-backend")
