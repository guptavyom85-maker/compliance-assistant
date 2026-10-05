from functools import lru_cache
import numpy as np
from django.conf import settings

@lru_cache(maxsize=2)
def get_embedder(model_name=None):
    from sentence_transformers import SentenceTransformer
    from transformers.utils import logging as transformers_logging
    # A checkpoint load report about buffers such as `position_ids` is not a
    # model failure. Keep routine startup output quiet while preserving raised
    # exceptions, then avoid a Hub request when the model is already cached.
    transformers_logging.set_verbosity_error()
    transformers_logging.disable_progress_bar()
    name = model_name or settings.EMBEDDING_MODEL
    try:
        return SentenceTransformer(name, local_files_only=True)
    except Exception:
        # A fresh installation still downloads normally. HF_TOKEN is optional
        # and only affects Hub rate limits for that first download.
        return SentenceTransformer(name)

def embed_texts(texts):
    if not texts:
        return np.empty((0, settings.EMBEDDING_DIMENSION), dtype='float32')
    return np.asarray(get_embedder(settings.EMBEDDING_MODEL).encode(
        texts, normalize_embeddings=True, batch_size=32), dtype='float32')

def embed_query(query):
    return embed_texts([query])[0]
