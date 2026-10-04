from functools import lru_cache
import numpy as np
from django.conf import settings

@lru_cache(maxsize=2)
def get_embedder(model_name=None):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(model_name or settings.EMBEDDING_MODEL)

def embed_texts(texts):
    if not texts:
        return np.empty((0, settings.EMBEDDING_DIMENSION), dtype='float32')
    return np.asarray(get_embedder(settings.EMBEDDING_MODEL).encode(
        texts, normalize_embeddings=True, batch_size=32), dtype='float32')

def embed_query(query):
    return embed_texts([query])[0]
