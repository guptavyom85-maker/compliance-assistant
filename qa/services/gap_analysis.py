from collections import Counter
from django.utils import timezone
from qa.models import Document, Obligation, GapAnalysisRun, GapFinding
from rag.schemas import GapJudgment
from rag.generator import structured_call
from rag.prompts import UNTRUSTED
from rag.vectorstore import VectorStore, corpus_lock
from rag.retriever import search_documents, evidence_dict
from .obligations import source_current, eligible_source

GAP_VERSION = 'gap-1'


def run_gap_analysis(policy_id, regulatory_ids, user=None):
    policy = Document.objects.get(pk=policy_id)
    if policy.document_type != 'company_policy' or not policy.is_indexed:
        raise ValueError('Select an indexed company-policy document.')
    documents = list(Document.objects.filter(pk__in=regulatory_ids))
    if not documents or any(not eligible_source(d) for d in documents):
        raise ValueError('Select in-force binding regulatory sources.')
    obligations = list(Obligation.objects.filter(source_document__in=documents,
        review_status__in=['confirmed', 'edited'], reviewed_at__isnull=False, reviewer__isnull=False,
        entailment_status='entailed', quote_verified=True).select_related('source_document'))
    if not obligations:
        raise ValueError('No human-confirmed obligations are available for this scope.')
    with corpus_lock():
        manifest = VectorStore().manifest
    run = GapAnalysisRun.objects.create(policy_document=policy, created_by=user,
        corpus_fingerprint=manifest['corpus_fingerprint'], scope={'regulatory_ids': regulatory_ids},
        configuration={'prompt_version': GAP_VERSION, 'retrieval_mode': 'hybrid_rerank',
                       'policy_title': policy.title, 'policy_version': policy.version_label})
    run.regulatory_documents.set(documents)
    errors = 0
    for obligation in obligations:
        finding = GapFinding(run=run, obligation=obligation, status='needs_review', prompt_version=GAP_VERSION)
        try:
            with corpus_lock():
                store = VectorStore()
                if store.manifest['corpus_fingerprint'] != run.corpus_fingerprint:
                    raise ValueError('Corpus changed during analysis.')
                source = source_current(obligation)
                if source is None:
                    raise ValueError('Confirmed obligation source is stale.')
                finding.regulatory_evidence = dict(**evidence_dict(source), obligation_text=obligation.obligation_text,
                    obligated_party=obligation.obligated_party, condition=obligation.condition,
                    deadline_or_trigger=obligation.deadline_or_trigger)
            candidates = search_documents(obligation.obligation_text, document_ids=[policy.pk],
                document_type='company_policy', mode='hybrid_rerank', store=store)
            finding.candidate_policy_chunk_ids = [c['chunk_id'] for c in candidates]
            judge, meta = structured_call(UNTRUSTED + ''' Compare the supplied confirmed regulatory obligation
with candidate policy passages. Judge addressed, partially_addressed, not_addressed,
conflicting or needs_review. Preserve conditions, parties and deadlines. Cite one
provided policy_chunk_id for addressed/partially_addressed/conflicting. Otherwise
use null if no passage matches. Absence from retrieved passages is a potential gap,
not proof of non-compliance. Explain scope and uncertainty briefly.''',
                {'obligation': finding.regulatory_evidence, 'policy_candidates': candidates}, GapJudgment, judge=True)
            finding.model_name = meta['model']
            finding.status, finding.explanation, finding.confidence_band = judge.status, judge.explanation, judge.confidence
            matches = [c for c in candidates if c['chunk_id'] == judge.policy_chunk_id]
            if judge.policy_chunk_id is not None and not matches:
                raise ValueError('Judge cited a passage outside the candidates.')
            if judge.status in ('addressed', 'partially_addressed', 'conflicting') and not matches:
                raise ValueError('A matched finding needs policy evidence.')
            if matches:
                finding.matched_policy_chunk_id = matches[0]['chunk_id']
                finding.policy_evidence = matches[0]
            if judge.confidence == 'low':
                finding.status = 'needs_review'
        except Exception as exc:
            finding.status, finding.confidence_band = 'needs_review', 'low'
            finding.error = type(exc).__name__
            finding.explanation = 'Analysis incomplete; source/model/index verification failed. Human review required.'
            errors += 1
        finding.save()
    run.counts = dict(Counter(run.findings.values_list('status', flat=True)))
    run.configuration['automated_counts'] = run.counts.copy()
    run.configuration['error_count'] = errors
    run.error = f'{errors} findings could not be assessed.' if errors else ''
    run.status, run.finished_at = ('failed' if errors else 'completed'), timezone.now()
    run.save()
    return run
