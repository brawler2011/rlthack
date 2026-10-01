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

## Quick Start (demo)

Needs Docker (for PostgreSQL), Python 3.11 with Poetry, Bun and [Task](https://taskfile.dev).

```bash
task setup      # Python and frontend dependencies
# put the dataset CSVs into data/Данные 24-25/ (file names don't matter: detected by columns)
task pipeline   # once, ~35 min: PostgreSQL, CSV load, FNS SME registry, embeddings, ranker
task demo       # API http://localhost:8000 (/docs) + UI http://localhost:5173
```

The API is up at once; the matching engine loads in the background for about a minute —
`GET /api/v1/health` shows `"engine": "ready"` when search works.

| Step of `task pipeline` | Takes | Produces |
| :--- | :--- | :--- |
| `01_init_db` | ~1.5 min | `lots`, `lot_items`, `bids` from the CSVs + data quality report |
| `02_aggregate_profiles` | ~1 min | supplier marts (WinRate over contested lots, OKPD2 and customer history) |
| `03_enrich_roles --download` | ~15 min (2.1 GB download) | 490k SME registry companies of SPb / LO with roles |
| `04_build_embeddings` | ~16 min on 4 CPU cores | vectors of 414k unique lot texts |
| `05_train_ranker` | ~3 min | CatBoost ranker |

`docker compose up --build` builds the all-in-one image (API + UI on :8000) and mounts `data/` and
`backend/models/`, so run `task pipeline` first. The image pulls PyTorch and is large.

## Quality

Offline evaluation (`task eval`, `scripts/07_evaluate_expansion.py`): the model only sees bids
before 2025-10-01 and ranks suppliers for 2000 later lots.

| Method | Winner in top 1 | top 10 | top 20 | MRR@20 |
| :--- | ---: | ---: | ---: | ---: |
| OKPD2 prefixes only (baseline) | 9% | 35% | 47% | 0.17 |
| Vectors (similar past lots) | 24% | 57% | 63% | 0.34 |
| Vectors + customer history + OKPD2 | 30% | 61% | 68% | 0.40 |
| **+ CatBoost ranker** | **37%** | **67%** | **73%** | **0.47** |

- Any real bidder of the lot in our top 10: 74% of lots, 81% on the e-shop (only e-shop data lists
  losing bidders).
- 5% of winners never bid before: for them the SME registry is the source. 72% of them are in it;
  their OKVED group is among the 10 we expect for the lot in 42% of cases.
- Roles (manufacturer / distributor / supplier) from the registry OKVED: 60% of the suppliers in the
  data; the rest are large companies outside the SME registry.

## Development

* Backend with autoreload: `task dev:backend`; frontend: `task dev:frontend`
* Linters (Ruff + ESLint): `task lint`; formatting: `task format`, `task format:check`
* Tests: `task test` (database tests need `TEST_DATABASE_URL`, see `backend/README.md`)
* All commands: `task --list`
