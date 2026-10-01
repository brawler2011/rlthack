# Backend — Intelligent Counterparty Selection Service

FastAPI backend, PostgreSQL storage, and ML pipelines (CatBoost Ranker, Sentence-Transformers, SHAP).

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
