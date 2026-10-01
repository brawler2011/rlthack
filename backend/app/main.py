from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.config import settings
from app.core.database import close_db, open_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # PostgreSQL connection pool
    open_db()
    yield
    # Close resources
    close_db()


app = FastAPI(
    title="Roseltorg • Intelligent Counterparty Selection Service AIS GZ",
    description="Recommendation service and Explainable AI (XAI) API for counterparty matching",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(api_router)

# Serve frontend static assets (if built)
if settings.static_dir.exists():
    app.mount("/", StaticFiles(directory=str(settings.static_dir), html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app", host=settings.app_host, port=settings.app_port, reload=settings.debug
    )
