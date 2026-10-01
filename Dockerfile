# ==========================================
# Stage 1: Build Frontend (Bun + React + Vite)
# ==========================================
FROM oven/bun:1.1-alpine AS frontend-builder
WORKDIR /app/frontend

# Установка зависимостей фронтенда
COPY frontend/package.json frontend/bun.lockb* ./
RUN bun install --frozen-lockfile || bun install

# Сборка статических файлов
COPY frontend/ ./
RUN bun run build

# ==========================================
# Stage 2: Backend & Runtime (Python + FastAPI)
# ==========================================
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=1.8.3 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    PORT=8000

WORKDIR /app

# Системные пакеты для сборки ML-библиотек
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Установка Poetry
RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

# Установка зависимостей бэкенда
COPY backend/pyproject.toml backend/poetry.lock* ./backend/
WORKDIR /app/backend
RUN poetry install --only main --no-root

WORKDIR /app

# Копирование исходного кода бэкенда и скриптов
COPY backend /app/backend

# Копирование скомпилированного фронтенда из Stage 1 в static бэкенда
COPY --from=frontend-builder /app/frontend/dist /app/backend/app/static

# Директории для данных
RUN mkdir -p /app/data/processed /app/data/dictionaries

EXPOSE 8000

# Запуск приложения
CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
