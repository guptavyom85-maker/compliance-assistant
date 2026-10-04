from django.conf import settings
from .vectorstore import VectorStore, corpus_lock
from .lexical import search as lexical_search
from .reranker import rerank

def evidence_dict(c):
    return dict(chunk_id=c.id, document_id=c.document_id, document_title=c.document.title,
                document_type=c.document.document_type, document_status=c.document.status,
                source_category=c.document.source_category, paragraph_id=c.paragraph_id,
                start_page=c.start_page, end_page=c.end_page,
                printed_pages=c.printed_span, text=c.text, content_sha256=c.content_sha256)

def fuse(dense, lexical, k=60, dense_weight=1., lexical_weight=1.):
    scores = {}
    for source, ranked, weight in [('dense', dense, dense_weight), ('bm25', lexical, lexical_weight)]:
        for rank, (identifier, score) in enumerate(ranked, 1):
            item = scores.setdefault(identifier, {'chunk_id': identifier, 'score': 0.})
            item['score'] += weight / (k + rank)
            item[source + '_score'] = score
            item[source + '_rank'] = rank
    return sorted(scores.values(), key=lambda c: (-c['score'], c['chunk_id']))

def search_documents(query, document_ids=None, top_k=None, mode=None, document_type='regulation', store=None, threshold=None):
    if store is None:
        with corpus_lock():
            snapshot = VectorStore()
        # The generation and ORM rows are immutable snapshots for this request.
        # Do not hold the corpus writer lock during slow model initialization.
        return search_documents(query, document_ids, top_k, mode, document_type, snapshot, threshold)
    top_k = top_k or settings.RAG_TOP_K
    mode = mode or settings.RAG_RETRIEVAL_MODE
    threshold = settings.RAG_CONFIDENCE_THRESHOLD if threshold is None else threshold
    if mode not in ('dense', 'hybrid', 'hybrid_rerank'):
        raise ValueError('Unknown retrieval mode.')
    allowed = {c.id: c for c in store.rows if c.document.document_type == document_type
               and (not document_ids or c.document_id in document_ids)}
    # Apply filters before candidate truncation, important when a policy shares the index.
    dense = [(i, s) for i, s in store.search(query, max(1, len(store.rows))) if i in allowed and s >= threshold]
    if mode == 'dense':
        return [dict(**evidence_dict(allowed[i]), score=s, dense_score=s) for i, s in dense[:top_k]]
    dense = dense[:settings.RAG_DENSE_CANDIDATES]
    lexical = lexical_search(query, list(allowed.values()), settings.RAG_BM25_CANDIDATES)
    candidates = [dict(**evidence_dict(allowed[c['chunk_id']]), **{k:v for k,v in c.items() if k != 'chunk_id'})
                  for c in fuse(dense, lexical, settings.RAG_RRF_K, settings.RAG_DENSE_WEIGHT, settings.RAG_BM25_WEIGHT)]
    if mode == 'hybrid':
        return candidates[:top_k]
    return [c for c in rerank(query, candidates[:settings.RAG_RERANK_CANDIDATES], top_k)
            if c['reranker_score'] >= settings.RAG_RERANK_MIN_SCORE]

def retrieve(query, vector_store, top_k=5, threshold=.3):
    return search_documents(query, top_k=top_k, mode='dense', store=vector_store, threshold=threshold)
