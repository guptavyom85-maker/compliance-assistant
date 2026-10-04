"""Reviewed ground truth is mandatory; missing judgments remain unavailable."""
import math
import statistics
import time
from django.conf import settings
from qa.models import GoldQuestion, EvalRun, EvalResult
from rag.pipeline import answer_question
from rag.schemas import CorrectnessJudgment
from rag.generator import structured_call
from rag.prompts import CORRECTNESS, CORRECTNESS_VERSION
from rag.vectorstore import VectorStore, corpus_lock

def matching_chunks(evidence):
    chunks = evidence.document.chunks.filter(paragraph_id=evidence.paragraph_id)
    if evidence.text_anchor:
        chunks = chunks.filter(text__contains=evidence.text_anchor)
    return list(chunks)

def validate_gold(questions, require_review=True):
    errors = []
    for q in questions:
        if require_review and (not q.reviewed_at or not q.reviewed_by_id):
            errors.append(f'Question {q.pk}: requires human review.')
        evidence = list(q.evidence.filter(required=True).select_related('document'))
        if q.is_answerable and (not evidence or not q.expected_answer.strip()):
            errors.append(f'Question {q.pk}: reference answer and required evidence needed.')
        for e in evidence:
            if not matching_chunks(e):
                errors.append(f'Question {q.pk}: evidence {e.pk} no longer resolves.')
    return errors

def retrieval_metrics(ranked, evidence):
    ranks, found = [], 0
    for item in evidence:
        hits = [n for n, c in enumerate(ranked, 1)
                if c['document_id'] == item.document_id and c['paragraph_id'] == item.paragraph_id
                and (not item.text_anchor or item.text_anchor in c['text'])]
        if hits:
            ranks.append(min(hits))
            found += 1
    return (min(ranks) if ranks else None, found / len(evidence) if evidence else None)

def mean(values):
    items = [v for v in values if v is not None]
    return statistics.mean(items) if items else None

def run_evaluation(label='evaluation', split='test', mode='dense', allow_unreviewed=False, retrieval_only=False):
    questions = list(GoldQuestion.objects.filter(is_active=True, split=split).prefetch_related('evidence'))
    if not questions:
        raise ValueError(f'No active questions in {split} split.')
    errors = validate_gold(questions, require_review=not allow_unreviewed)
    if errors:
        raise ValueError('Evaluation blocked: ' + ' '.join(errors))
    with corpus_lock():
        manifest = VectorStore().manifest
    config = dict(mode=mode, split=split, top_k=settings.RAG_TOP_K, provisional=allow_unreviewed,
                  retrieval_only=retrieval_only, reranker_model=settings.RERANKER_MODEL,
                  rrf_k=settings.RAG_RRF_K, dense_candidates=settings.RAG_DENSE_CANDIDATES,
                  lexical_candidates=settings.RAG_BM25_CANDIDATES,
                  threshold=settings.RAG_CONFIDENCE_THRESHOLD, corpus_fingerprint=manifest['corpus_fingerprint'],
                  embedding_model=manifest['embedding_model'], answer_model=settings.OPENROUTER_MODEL,
                  judge_model=settings.OPENROUTER_JUDGE_MODEL, judge_prompt_version=CORRECTNESS_VERSION,
                  gold_snapshot=[dict(id=q.pk, question=q.question, reference=q.expected_answer,
                    category=q.category, version=q.gold_set_version,
                    evidence=list(q.evidence.values('document_id', 'paragraph_id', 'text_anchor', 'required'))) for q in questions])
    run = EvalRun.objects.create(label=label, configuration=config, total_questions=len(questions), status='running')
    rows = []
    for q in questions:
        started = time.monotonic()
        row = EvalResult(eval_run=run, gold_question=q, answer_quality='not_judged')
        try:
            if retrieval_only:
                from rag.retriever import search_documents
                with corpus_lock():
                    store = VectorStore()
                    if store.manifest['corpus_fingerprint'] != manifest['corpus_fingerprint']:
                        raise ValueError('Corpus changed during evaluation')
                passages = search_documents(q.question, mode=mode, store=store)
                row.retrieved_evidence = passages
                row.retrieved_chunk_ids = [c['chunk_id'] for c in passages]
                if q.is_answerable:
                    row.hit_rank, row.recall_at_k = retrieval_metrics(passages, list(q.evidence.filter(required=True)))
                    row.retrieval_correct = row.recall_at_k == 1
                row.response_time_ms = round((time.monotonic() - started) * 1000)
                row.save()
                rows.append(row)
                continue
            result = answer_question(q.question, mode=mode)
            if result['retrieval_config']['corpus_fingerprint'] != manifest['corpus_fingerprint']:
                raise ValueError('Corpus changed during evaluation')
            row.system_answer, row.answer_payload = result['answer'], result['answer_payload']
            row.retrieved_chunk_ids = [c['chunk_id'] for c in result['chunks']]
            row.retrieved_evidence = result['chunks']
            row.refused = result['not_found']
            row.refusal_correct = row.refused == (not q.is_answerable)
            row.faithfulness_score, row.citation_precision = result['faithfulness_score'], result['citation_precision']
            if q.is_answerable:
                row.hit_rank, row.recall_at_k = retrieval_metrics(result['chunks'], list(q.evidence.filter(required=True)))
                row.retrieval_correct = row.recall_at_k == 1
                if row.refused:
                    row.correctness_label, row.correctness_score = 'wrong', 0
                    row.answer_quality = 'false_refuse'
                else:
                    judge, metadata = structured_call(CORRECTNESS, dict(question=q.question,
                        reference=q.expected_answer, required_evidence=[
                            [dict(text=c.text, document_id=c.document_id, paragraph_id=c.paragraph_id) for c in matching_chunks(e)]
                            for e in q.evidence.filter(required=True)],
                        answer=result['answer_payload']), CorrectnessJudgment, judge=True)
                    row.correctness_label = row.answer_quality = judge.label
                    row.correctness_score = {'correct': 1.0, 'partial': 0.5, 'wrong': 0.0}[judge.label]
                    row.judge_model, row.judge_prompt_version = metadata['model'], CORRECTNESS_VERSION
                    row.judge_explanation = judge.explanation
            else:
                row.answer_quality = 'refused' if row.refused else 'wrong'
            row.unsupported_claim_ids = [c['claim_id'] for c in result['answer_payload']['claims'] if c['support']['status'] != 'supported']
        except Exception as exc:
            row.error = type(exc).__name__
        row.response_time_ms = round((time.monotonic() - started) * 1000)
        row.save()
        rows.append(row)
    answerable = [r for r in rows if r.gold_question.is_answerable]
    unanswerable = [r for r in rows if not r.gold_question.is_answerable]
    # Failed retrievals count as misses; unavailable judge results are reported separately.
    run.retrieval_hit_at_1 = mean([int(r.hit_rank is not None and r.hit_rank <= 1) for r in answerable])
    run.retrieval_hit_at_3 = mean([int(r.hit_rank is not None and r.hit_rank <= 3) for r in answerable])
    run.retrieval_hit_at_k = mean([int(r.hit_rank is not None) for r in answerable])
    run.retrieval_recall_at_k = mean([r.recall_at_k if r.recall_at_k is not None else 0 for r in answerable])
    run.retrieval_mrr = mean([1 / r.hit_rank if r.hit_rank else 0 for r in answerable])
    run.answer_correctness = mean([r.correctness_score for r in answerable])
    # Pool substantive claims/citations; long answers must not get the same
    # weighting as a one-claim answer. Unknown validation stays excluded/reported.
    judged_claims = [c for r in rows if r.faithfulness_score is not None
                     for c in r.answer_payload.get('claims', [])]
    run.faithfulness = mean([int(c['support']['status'] == 'supported') for c in judged_claims])
    citation_total = sum(len(set(c['supporting_chunk_ids'])) for c in judged_claims)
    citation_supported = sum(len(set(c['support']['supporting_chunk_ids'])) for c in judged_claims
                             if c['support']['status'] in ('supported', 'partial'))
    run.citation_precision = citation_supported / citation_total if citation_total else None
    run.correct_refusal_rate = None if retrieval_only else mean([int(r.refused and not r.error) for r in unanswerable])
    run.false_refusal_rate = None if retrieval_only else mean([int(r.refused and not r.error) for r in answerable])
    timings = sorted(r.response_time_ms for r in rows)
    run.avg_response_time_ms = statistics.mean(timings)
    run.median_latency_ms = statistics.median(timings)
    run.p95_latency_ms = timings[max(0, math.ceil(len(timings) * .95) - 1)]
    run.configuration['coverage'] = dict(total=len(rows), errors=sum(bool(r.error) for r in rows),
        correctness_judged=sum(r.correctness_score is not None for r in answerable),
        faithfulness_judged=sum(r.faithfulness_score is not None for r in rows))
    run.status = 'partial' if any(r.error for r in rows) else ('provisional' if allow_unreviewed else 'complete')
    run.save()
    return run
