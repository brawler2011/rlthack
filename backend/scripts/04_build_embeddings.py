"""Script 04: Embed unique lot texts (cleaned subject + item names) with a local sentence model."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from app.config import settings  # noqa: E402
from app.etl import pipeline  # noqa: E402
from app.ml.semantic_retriever import LotEmbeddings, encode, load_model  # noqa: E402
from app.ml.text import lot_text  # noqa: E402

LOTS_QUERY = """
SELECT l.lot_id, l.subject,
       (array_agg(DISTINCT i.product_name) FILTER (WHERE i.product_name IS NOT NULL))[1:10]
FROM lots l
LEFT JOIN lot_items i USING (lot_id)
GROUP BY l.lot_id
ORDER BY l.lot_id
"""


def main():
    with pipeline.connect() as conn, pipeline.timed("[04] Reading lots"):
        rows = conn.execute(LOTS_QUERY).fetchall()

    text_ids: dict[str, int] = {}
    lot_text_ids = np.array(
        [
            text_ids.setdefault(lot_text(subject, names or []), len(text_ids))
            for _, subject, names in rows
        ],
        dtype=np.int32,
    )
    print(f"    lots: {len(rows)}, unique texts: {len(text_ids)}")

    with pipeline.timed(f"[04] Embedding with {settings.transformer_model_name}"):
        vectors = encode(load_model(), list(text_ids), progress=True)

    lot_ids = np.array([row[0] for row in rows], dtype=np.int64)
    LotEmbeddings(vectors, lot_ids, lot_text_ids).save(settings.embeddings_dir)
    print(f"    saved to {settings.embeddings_dir}")


if __name__ == "__main__":
    main()
