from fastapi import APIRouter

from app.api.v1 import batch, enrichment, lots, suppliers

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(suppliers.router)
api_router.include_router(lots.router)
api_router.include_router(enrichment.router)
api_router.include_router(batch.router)


@api_router.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "rlthack-recsys-backend"}
