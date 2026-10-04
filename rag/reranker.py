from functools import lru_cache
from django.conf import settings


@lru_cache(maxsize=2)
def get_reranker(name):
    from sentence_transformers import CrossEncoder
    return CrossEncoder(name, max_length=512)


def rerank(query, candidates, top_k=5):
    if not candidates:
        return []
    scores = get_reranker(settings.RERANKER_MODEL).predict([(query, c['text']) for c in candidates])
    result = [dict(c, reranker_score=float(s)) for c, s in zip(candidates, scores)]
    return sorted(result, key=lambda c: (-c['reranker_score'], c['chunk_id']))[:top_k]
