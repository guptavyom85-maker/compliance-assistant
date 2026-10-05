import re
from django.conf import settings
from .vectorstore import VectorStore, corpus_lock
from .lexical import search as lexical_search
from .reranker import rerank

LIST_INTRO_RE = re.compile(
    r'\b(?:following|below)\b.{0,120}\b(?:measures|changes|proposals|steps|requirements|principles)\b'
    r'|\bas follows\b',
    re.IGNORECASE | re.DOTALL,
)
NUMERIC_CLAUSE_RE = re.compile(r'^\d+(?:\.\d+)*\.?$')

def evidence_dict(c):
    return dict(chunk_id=c.id, document_id=c.document_id, document_title=c.document.title,
                document_type=c.document.document_type, document_status=c.document.status,
                source_category=c.document.source_category, paragraph_id=c.paragraph_id,
                start_page=c.start_page, end_page=c.end_page,
                printed_pages=c.printed_span, text=c.text, content_sha256=c.content_sha256)


def _numeric_clause_path(paragraph_id):
    value = (paragraph_id or '').strip()
    if not NUMERIC_CLAUSE_RE.fullmatch(value):
        return None
    return tuple(int(part) for part in value.rstrip('.').split('.'))


def expand_structural_context(ranked, store, max_chunks=None):
    """Add numbered child clauses when a retrieved passage introduces a list.

    Semantic ranking often retrieves a sentence such as "the following measures"
    while omitting the adjacent 5.1, 5.2, ... chunks that contain the answer. This
    expansion is deliberately narrow: it only follows numeric descendants within
    the same document and stops at the next section. Ranked hits remain identified
    separately so retrieval evaluation can still measure the configured top-k.
    """
    max_chunks = max_chunks or getattr(settings, 'RAG_MAX_CONTEXT_CHUNKS', 20)
    expanded = [dict(item, retrieval_role=item.get('retrieval_role', 'ranked')) for item in ranked]
    if not expanded or len(expanded) >= max_chunks:
        return expanded[:max_chunks]

    seen = {item['chunk_id'] for item in expanded}
    rows_by_document = {}
    for row in sorted(store.rows, key=lambda item: (item.document_id, item.chunk_index, item.id)):
        rows_by_document.setdefault(row.document_id, []).append(row)

    for anchor in ranked:
        if len(expanded) >= max_chunks or not LIST_INTRO_RE.search(anchor.get('text', '')):
            continue
        anchor_path = _numeric_clause_path(anchor.get('paragraph_id'))
        if not anchor_path:
            continue
        rows = rows_by_document.get(anchor['document_id'], [])
        anchor_position = next((n for n, row in enumerate(rows) if row.id == anchor['chunk_id']), None)
        if anchor_position is None:
            continue

        found_descendant = False
        for row in rows[anchor_position + 1:]:
            path = _numeric_clause_path(row.paragraph_id)
            if path:
                is_descendant = len(path) > len(anchor_path) and path[:len(anchor_path)] == anchor_path
                if not is_descendant:
                    # Once the numbered list starts, its next sibling/section is a
                    # reliable structural boundary. Before it starts, do not roam.
                    break
                found_descendant = True
            elif not found_descendant:
                break

            if row.id not in seen:
                item = evidence_dict(row)
                item.update(
                    score=anchor.get('score', 0),
                    retrieval_role='structural_neighbor',
                    expanded_from_chunk_id=anchor['chunk_id'],
                )
                expanded.append(item)
                seen.add(row.id)
                if len(expanded) >= max_chunks:
                    break
    return expanded

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
    allowed = {c.id: c for c in store.rows if (document_type is None or c.document.document_type == document_type)
               and (document_ids is None or c.document_id in document_ids)}
    if not allowed:
        return []
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
