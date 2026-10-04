"""Deterministic lexical candidates; terms preserve clause numbers and hyphens."""
import re
from rank_bm25 import BM25Okapi


def tokens(text):
    return re.findall(r'[\w]+(?:[.\-][\w]+)*', text.lower())


def search(query, chunks, top_k=20):
    if not chunks:
        return []
    model = BM25Okapi([tokens(c.text) or ['__empty__'] for c in chunks])
    scores = model.get_scores(tokens(query))
    ranked = sorted(zip(chunks, scores), key=lambda pair: (-pair[1], pair[0].id))
    return [(c.id, float(score)) for c, score in ranked[:top_k] if score > 0]
