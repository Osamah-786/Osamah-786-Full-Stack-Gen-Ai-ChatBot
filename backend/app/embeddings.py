"""Local embeddings shared by document ingestion and query retrieval."""

from functools import lru_cache
from typing import Sequence


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DIMENSIONS = 384
MAX_TOKENS = 254


@lru_cache(maxsize=1)
def _load_model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("Install the backend dependencies to use local embeddings") from exc

    try:
        return SentenceTransformer(MODEL_NAME)
    except OSError as exc:
        raise RuntimeError(
            f"Unable to load {MODEL_NAME}; check model cache or Hugging Face access"
        ) from exc


def embed_documents(texts: Sequence[str], *, batch_size: int = 32) -> list[list[float]]:
    """Embed a batch of document chunks with normalized 384-dimensional vectors."""
    if not texts:
        return []

    vectors = _load_model().encode(
        list(texts),
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    result = [[float(value) for value in vector] for vector in vectors]
    if len(result) != len(texts) or any(len(vector) != DIMENSIONS for vector in result):
        raise RuntimeError(f"Embedding model must return {DIMENSIONS}-dimensional vectors")
    return result


def embed_query(text: str) -> list[float]:
    """Embed a retrieval query with the same model and normalization as documents."""
    return embed_documents([text])[0]
