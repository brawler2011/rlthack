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
task pipeline   # once, ~45 min: PostgreSQL, CSV load, FNS SME registry, embeddings, ranker
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
| `05_train_ranker` | ~11 min | CatBoost ranker |

`docker compose up --build` builds the all-in-one image (API + UI on :8000) and mounts `data/` and
`backend/models/`, so run `task pipeline` first. The image pulls PyTorch and is large.

## Quality

Offline evaluation (`task eval`, `scripts/07_evaluate_expansion.py`): 2000 random lots published
after 2025-10-01. For each lot the model sees only bids before the start of the lot's month, as the
API does. The ranker is trained on July–September 2025; its settings were picked on a validation
split (trained on April–June, checked on July–September) without looking at these lots.

| Method | Winner in top 1 | top 10 | top 20 | MRR@20 |
| :--- | ---: | ---: | ---: | ---: |
| OKPD2 prefixes only (baseline) | 9% | 36% | 48% | 0.18 |
| Vectors (similar past lots) | 21% | 56% | 66% | 0.32 |
| Vectors + customer history + OKPD2 | 28% | 62% | 70% | 0.39 |
| **+ CatBoost ranker** | **42%** | **73%** | **79%** | **0.52** |

- The previous ranker scored 38% / 70% / 75% at top 1 / 10 / 20 under the same evaluation. The gain
  comes from repeat purchases (whether the supplier won this customer's lots most similar to the
  query, and how long ago), a pool of 200 candidates instead of 100 (on validation the winner is in
  it for 82% of lots instead of 74%) and the QuerySoftMax loss.
- Any real bidder of the lot in our top 10: 80% of lots, 87% on the e-shop (only e-shop data lists
  losing bidders).
- 4.8% of the lots are won by a company that never bid before. For them the SME registry of
  SPb / LO is the only source, and it holds the winner of 43% of these lots. The winner's OKVED
  group is among the 10 we expect for the lot in 42% of cases, and the winner is among the top
  100 suggested new companies for 1.4% of these lots (top 50: 0.8%): the pool has ~350k
  companies and the registry has almost nothing that tells a future winner apart.
- Roles (manufacturer / distributor / supplier) from the registry OKVED: 60% of the suppliers in the
  data; the rest are large companies outside the SME registry.

## Development

* Backend with autoreload: `task dev:backend`; frontend: `task dev:frontend`
* Linters (Ruff + ESLint): `task lint`; formatting: `task format`, `task format:check`
* Tests: `task test` (database tests need `TEST_DATABASE_URL`, see `backend/README.md`)
* All commands: `task --list`
