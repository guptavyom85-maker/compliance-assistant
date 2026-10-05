"""Selectable retrieval and bounded agents with structured evidence validation."""
from django.conf import settings
from .vectorstore import VectorStore, corpus_lock
from .generator import structured_call
from .schemas import Answer
from .faithfulness import check_claims
from .prompts import ANSWER, ANSWER_VERSION, SUPPORT_VERSION
from .retriever import search_documents, expand_structural_context
from .confidence import assess
from django.utils import timezone

def evidence_dict(c):
    return dict(chunk_id=c.id, document_id=c.document_id, document_title=c.document.title,
                document_type=c.document.document_type, document_status=c.document.status,
                source_category=c.document.source_category, paragraph_id=c.paragraph_id,
                start_page=c.start_page, end_page=c.end_page,
                printed_pages=c.printed_span, text=c.text, content_sha256=c.content_sha256)

def answer_question(question, vector_store_dir=None, api_key=None, top_k=None, threshold=None, mode=None,
                    use_agent=False, user=None, document_ids=None):
    top_k = top_k or settings.RAG_TOP_K
    threshold = settings.RAG_CONFIDENCE_THRESHOLD if threshold is None else threshold
    with corpus_lock(vector_store_dir):
        store = VectorStore(vector_store_dir)
        manifest = store.manifest
    scope_ids = None if document_ids is None else sorted({int(pk) for pk in document_ids})
    if scope_ids == []:
        raise ValueError('Select at least one indexed document.')
    available = {row.document_id for row in store.rows}
    if scope_ids is not None and not set(scope_ids).issubset(available):
        raise ValueError('A selected document is no longer available in the active index.')
    chunks = [] if use_agent else search_documents(question, document_ids=scope_ids, top_k=top_k,
        mode=mode, document_type=None if scope_ids is not None else 'regulation', store=store, threshold=threshold)
    agent_run = None
    if use_agent:
        from .agent import gather
        agent_run, chunks = gather(question, user, mode=mode, document_ids=scope_ids)
        try:
            with corpus_lock(vector_store_dir):
                latest = VectorStore(vector_store_dir)
                if latest.manifest['corpus_fingerprint'] != manifest['corpus_fingerprint']:
                    chunks = []
                    agent_run.error = 'CorpusChanged'
        except Exception:
            chunks = []
            agent_run.error = 'IndexValidationUnavailable'
    if chunks:
        chunks = expand_structural_context(chunks, store)
    meta, check = {'model': '', 'estimated_cost': None}, None
    if chunks and agent_run:
        from .agent import bounded_call
        from qa.models import AgentStep
        remaining = settings.RAG_AGENT_TOTAL_TIMEOUT_SECONDS - (timezone.now() - agent_run.started_at).total_seconds()
        try:
            output = bounded_call('synthesize', {'question': question, 'passages': chunks}, remaining)
            answer, meta, check = Answer.model_validate(output['answer']), output['metadata'], output['support']
            AgentStep.objects.create(run=agent_run, position=agent_run.step_count + 1, step_type='synthesis',
                output_summary='Structured answer and claim support checks completed.', evidence_chunk_ids=[c['chunk_id'] for c in chunks])
        except Exception as exc:
            agent_run.error = type(exc).__name__
            answer = Answer(answerable=False, claims=[], reason='The bounded agent could not complete verified synthesis in its time budget.')
            AgentStep.objects.create(run=agent_run, position=agent_run.step_count + 1, step_type='decision',
                output_summary=answer.reason, error=agent_run.error)
    elif chunks:
        answer, meta = structured_call(ANSWER, {'question': question, 'passages': chunks}, Answer, api_key=api_key)
    else:
        answer = Answer(answerable=False, claims=[], reason='No sufficient passages found in the loaded sources.')
    if check is None:
        check = check_claims(answer, chunks, api_key)
    checks = {c['claim_id']: c for c in check['claims']}
    claims = []
    for claim in answer.claims:
        item = claim.model_dump()
        item['support'] = checks[claim.claim_id]
        item['sources'] = [c for c in chunks if c['chunk_id'] in claim.supporting_chunk_ids]
        claims.append(item)
    # No model self-confidence is used. Full semantic support is not a probability.
    confidence, review_required, reason = assess(answer, check, chunks)
    payload = dict(answerable=answer.answerable, reason=answer.reason, claims=claims,
                   confidence_band=confidence, requires_human_review=review_required, review_reason=reason,
                   evidence_snapshot=chunks, generation_metadata=meta, support_metadata=check['metadata'])
    if agent_run:
        agent_run.final_answer_payload = payload
        agent_run.status = 'completed' if answer.answerable else 'abstained'
        agent_run.finished_at = timezone.now()
        agent_run.save()
    return dict(answer='\n\n'.join(c.text for c in answer.claims) if answer.answerable else answer.reason,
                answer_payload=payload, chunks=chunks, not_found=not answer.answerable,
                citation_check=dict(verified=check['supported'], message='All claims supported by cited passages.' if check['supported'] else reason),
                faithfulness_score=check['faithfulness'], citation_precision=check['citation_precision'],
                retrieval_scores=[{'chunk_id': c['chunk_id'], 'score': c.get('score', 0)} for c in chunks],
                agent_run_id=agent_run.pk if agent_run else None,
                model_name=meta['model'], prompt_version=ANSWER_VERSION, estimated_cost=meta['estimated_cost'],
                retrieval_config=dict(mode=mode or settings.RAG_RETRIEVAL_MODE, top_k=top_k, threshold=threshold,
                                      document_ids=scope_ids,
                                      document_scope=[dict(id=row.document_id, title=row.document.title,
                                                           type=row.document.document_type,
                                                           category=row.document.source_category,
                                                           status=row.document.status)
                                                      for row in {r.document_id: r for r in store.rows
                                                                  if ((scope_ids is None and r.document.document_type == 'regulation')
                                                                      or (scope_ids is not None and r.document_id in scope_ids))}.values()],
                                      rrf_k=settings.RAG_RRF_K, reranker_model=settings.RERANKER_MODEL,
                                      corpus_fingerprint=manifest['corpus_fingerprint'],
                                      generation_id=manifest['generation_id'],
                                      embedding_model=manifest['embedding_model'],
                                      ranked_chunk_ids=[c['chunk_id'] for c in chunks
                                                        if c.get('retrieval_role') != 'structural_neighbor'],
                                      structural_context_chunk_ids=[c['chunk_id'] for c in chunks
                                                                    if c.get('retrieval_role') == 'structural_neighbor'],
                                      support_prompt_version=SUPPORT_VERSION))

def index_document(document_id, vector_store_dir=None):
    from qa.services.documents import index_document as index
    return index(document_id, vector_store_dir)
