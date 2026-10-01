from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.api.router import api_router
from app.core.database import get_db, close_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Инициализация / проверка базы данных DuckDB
    get_db()
    yield
    # Закрытие ресурсов
    close_db()

app = FastAPI(
    title="Росэлторг • Интеллектуальный сервис подбора поставщиков АИС ГЗ",
    description="API рекомендательного сервиса и Explainable AI (XAI) для подбора контрагентов",
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

# Подключение API маршрутов
app.include_router(api_router)

# Раздача статики фронтенда (если сбилжен)
if settings.static_dir.exists():
    app.mount("/", StaticFiles(directory=str(settings.static_dir), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=settings.debug)
