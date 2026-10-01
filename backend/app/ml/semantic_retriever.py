"""Semantic search over past lots: cleaned lot texts embedded with a local sentence model.

Only unique lot texts are embedded (many lots share a subject); lot_text_ids maps every lot to
its row in vectors. Plain .npy files opened with mmap, so API workers share one copy in memory.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.config import settings

FILES = ("vectors", "lot_ids", "lot_text_ids")


@dataclass
class LotEmbeddings:
    vectors: np.ndarray  # (texts, dim) float32, L2-normalized
    lot_ids: np.ndarray  # (lots,) int64
    lot_text_ids: np.ndarray  # (lots,) int32: row in vectors for each lot

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        for name in FILES:
            np.save(directory / f"{name}.npy", getattr(self, name))

    @classmethod
    def load(cls, directory: Path) -> "LotEmbeddings":
        return cls(*(np.load(directory / f"{name}.npy", mmap_mode="r") for name in FILES))


def load_model(name: str | None = None):
    from sentence_transformers import SentenceTransformer  # heavy import, only when needed

    model = SentenceTransformer(
        name or settings.transformer_model_name,
        device="cpu",
        cache_folder=str(settings.models_dir / "hf"),
    )
    model.max_seq_length = 128  # lot texts are short; longer inputs only cost time
    return model


def encode(model, texts: list[str], batch_size: int = 256, progress: bool = False) -> np.ndarray:
    vectors = model.encode(
        texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=progress
    )
    return np.asarray(vectors, dtype=np.float32)


def similar_texts(
    vectors: np.ndarray, query: np.ndarray, top_k: int
) -> tuple[np.ndarray, np.ndarray]:
    """Rows of the top_k texts most similar to the query vector and their cosine similarity."""
    sims = vectors @ query
    if top_k < len(sims):
        top = np.argpartition(-sims, top_k)[:top_k]
    else:
        top = np.arange(len(sims))
    return top, sims[top]
