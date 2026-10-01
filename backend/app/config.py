from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True

    # Пути
    base_dir: Path = Path(__file__).resolve().parent.parent.parent
    data_dir: Path = base_dir / "data"
    raw_data_dir: Path = data_dir / "Данные 24-25"
    processed_data_dir: Path = data_dir / "processed"
    dictionaries_dir: Path = data_dir / "dictionaries"
    static_dir: Path = Path(__file__).resolve().parent / "static"

    # PostgreSQL
    database_url: str = "postgresql://rlthack:rlthack@localhost:5432/rlthack"

    # ML Модели
    models_dir: Path = base_dir / "backend" / "models"
    catboost_model_path: Path = models_dir / "catboost_ranker.cbm"
    embeddings_cache_path: Path = processed_data_dir / "embeddings_cache.npz"
    transformer_model_name: str = "cointegrated/rubert-tiny2"

    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
    ]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
