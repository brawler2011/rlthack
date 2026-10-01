.PHONY: help setup data train dev-backend dev-frontend up down test clean

help:
	@echo "Команды проекта (Росэлторг Хакатон):"
	@echo "  make setup        - Установка зависимостей (Poetry и Bun)"
	@echo "  make data         - Запуск ETL и сборка DuckDB (4.5M строк)"
	@echo "  make train        - Построение эмбеддингов и обучение CatBoost"
	@echo "  make dev-backend  - Запуск FastAPI бэкенда в dev-режиме (порт 8000)"
	@echo "  make dev-frontend - Запуск Vite фронтенда в dev-режиме (порт 5173)"
	@echo "  make up           - Запуск All-in-one Docker контейнера (порт 8000)"
	@echo "  make down         - Остановка Docker контейнеров"
	@echo "  make test         - Запуск тестов бэкенда"
	@echo "  make clean        - Очистка временных файлов и кэша"

setup:
	cd backend && poetry install
	cd frontend && bun install

data:
	cd backend && poetry run python scripts/01_init_duckdb.py
	cd backend && poetry run python scripts/02_aggregate_profiles.py
	cd backend && poetry run python scripts/03_enrich_roles.py

train:
	cd backend && poetry run python scripts/04_build_embeddings.py
	cd backend && poetry run python scripts/05_train_ranker.py

dev-backend:
	cd backend && poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && bun run dev

up:
	docker compose up --build

down:
	docker compose down

test:
	cd backend && poetry run pytest tests/ -v

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	rm -rf frontend/dist
