import numpy as np
from sentence_transformers import SentenceTransformer

_EMBEDDER_INSTANCE = None

def get_embedder() -> SentenceTransformer:
    global _EMBEDDER_INSTANCE
    if _EMBEDDER_INSTANCE is None:
        _EMBEDDER_INSTANCE = SentenceTransformer('all-MiniLM-L6-v2')
    return _EMBEDDER_INSTANCE

def embed_texts(texts: list[str]) -> np.ndarray:
    if not texts:
        return np.array([])
    embedder = get_embedder()
    embeddings = embedder.encode(texts, normalize_embeddings=True)
    return embeddings

def embed_query(query: str) -> np.ndarray:
    embedder = get_embedder()
    embedding = embedder.encode([query], normalize_embeddings=True)
    return embedding[0]
