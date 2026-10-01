# Intelligent Counterparty Selection Service (Roseltorg)

Search, ranking, and verification service for relevant suppliers, manufacturers, and distributors for Saint Petersburg AIS GZ and electronic store.

## Tech Stack
* **Backend:** Python, FastAPI, PostgreSQL, CatBoost, Sentence-Transformers (`rubert-tiny2`), Rank-BM25, SHAP, Pydantic v2, Poetry
* **Frontend:** React, TypeScript, Bun, Vite, Tailwind CSS, Lucide Icons, Recharts
* **Infrastructure:** Docker, Docker Compose (Multi-stage All-in-one build)

---

## Architecture Overview

1. **Offline Preprocessing (PostgreSQL):**
   * One-time import of 4.5M rows from hackathon datasets (Procurement Notices, Suppliers, TRU products/works/services).
   * Aggregation of supplier feature marts: WinRate, contract volumes, average contract values, historical specialization by OKPD2 codes.
   * Enrichment with registries (OKVED, Minpromtorg GISP) with counterparty role classification (*Manufacturer / Distributor / General Supplier*).
   * Local training of `CatBoostRanker` based on historical wins (`is_winner`).

2. **Online Inference (< 300 ms):**
   * **Candidate Retrieval:** Hierarchical OKPD2 code filter (2, 4, 6 digits) + BM25 lexical search + semantic vector similarity via `rubert-tiny2`.
   * **Reranking:** CatBoost scoring of top candidates.
   * **Explainable AI (XAI):** Feature contribution computation via SHAP values with natural language justifications for top placement.

3. **Web Interface:**
   * Search / select procurement notice from database or manual entry of new lot parameters.
   * Interactive filters by counterparty roles, region (Saint Petersburg / Leningrad Region), SME (MSP) status, and WinRate.
   * Detailed XAI card ("Why Recommended") with SHAP feature impact visualization.
   * Background worker: automated monitoring and batch counterparty matching for newly published notices.

---

## Quick Start

### Option 1: Docker Compose (Recommended for evaluation)
```bash
docker compose up --build
```
The application will be accessible at: **http://localhost:8000** (API, Swagger `/docs`, and Web UI on a single port).

### Option 2: Local Development Setup

1. **Install dependencies:**
   ```bash
   task setup
   ```
2. **Initialize database and ML models:**
   Put the dataset CSVs into `data/Данные 24-25/` (file names don't matter: the file type is detected by its columns).
   ```bash
   task db:up
   task data
   task train
   ```
3. **Run services:**
   * Backend: `task dev:backend` (http://localhost:8000)
   * Frontend: `task dev:frontend` (http://localhost:5173)

4. **Code quality checks and tests:**
   * Run linters (Ruff + ESLint): `task lint`
   * Format code (Ruff + Prettier): `task format`
   * Check formatting: `task format:check`
   * Run tests: `task test`
   * View all available commands: `task --list`
