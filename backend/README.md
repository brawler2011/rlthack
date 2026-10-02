# Backend — Intelligent Counterparty Selection Service

FastAPI backend, PostgreSQL storage, and ML pipelines (CatBoost Ranker, Sentence-Transformers, SHAP).

## Dependencies

CI and Docker use Poetry 2.4.1. Commit `poetry.lock` whenever dependencies change;
generate it with this version (`poetry lock`) and validate it with `poetry check --lock`.
Installation uses the committed lock instead of resolving package versions on every run.

Full development setup, including ML libraries and test tools:

```bash
poetry install --with ml
```

`task setup:backend` runs this command. Docker installs only `main,ml`.
For CI checks without ML libraries, use a separate clean environment:

```bash
POETRY_VIRTUALENVS_IN_PROJECT=true poetry sync --only main,dev --no-root
```

This installs API dependencies, NumPy, SciPy, pytest, HTTPX, and Ruff. The complete test suite
and contract checks run without Torch, CUDA, CatBoost, or Sentence Transformers; heavy
imports happen only when loading or training models. `poetry sync` removes dependencies outside
the selected groups, so use the full setup command again before running the ML pipeline.

## Database

The schema lives in `app/etl/sql/`. `scripts/01_init_db.py` recreates it and loads the CSVs,
`scripts/02_aggregate_profiles.py` builds the supplier marts.

| Table | Contents |
| :--- | :--- |
| `stg_notices`, `stg_items`, `stg_bids` | CSVs as is, all columns text: to see why a row was dropped |
| `lots` | Procurement notices, one row per lot |
| `lot_items` | TRU items with OKPD2 code prefixes of 2, 4 and 6 digits |
| `bids` | Participations: one row per (lot, INN) pair with the win flag |
| `supplier_profile` | Supplier profile: bids, wins, WinRate, average check, region |
| `supplier_okpd2` | Supplier experience by OKPD2 code: candidates are selected from it |
| `supplier_customer` | Supplier bids and wins per customer |
| `supplier_text` | Most frequent TRU names of the supplier for text search |

Loader tests on a small dataset need a separate database (its schema gets recreated):

```bash
TEST_DATABASE_URL=postgresql://rlthack:rlthack@localhost:5432/rlthack_test poetry run pytest tests/
```

Detailed documentation and launch instructions are available in the root [README.md](../README.md).
