from pathlib import Path
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from filelock import FileLock
from qa.models import Document, Chunk, Obligation, ObligationExtractionRecord
from rag.schemas import Extraction, Answer
from rag.generator import structured_call
from rag.faithfulness import check_claims
from rag.prompts import UNTRUSTED
from rag.retriever import evidence_dict
from rag.vectorstore import VectorStore, corpus_lock

EXTRACTION_VERSION = 'obligations-1'
BINDING_CATEGORIES = ('binding_regulation', 'master_direction', 'circular')
FIELDS = ('obligation_text', 'obligated_party', 'condition', 'deadline_or_trigger')


def eligible_source(doc):
    return doc.document_type == 'regulation' and doc.status == 'in_force' and doc.source_category in BINDING_CATEGORIES


def source_current(obligation):
    if not eligible_source(obligation.source_document):
        return None
    return Chunk.objects.filter(document_id=obligation.source_document_id,
        content_sha256=obligation.source_content_sha256, paragraph_id=obligation.source_paragraph_id).first()


def check_obligation(text, quote, chunk):
    quote_verified = ' '.join(quote.split()) in ' '.join(chunk.text.split()) and bool(quote.strip())
    if not quote_verified:
        return False, 'not_entailed', 'The quoted passage does not occur in the source.'
    answer = Answer(answerable=True, reason='', claims=[dict(claim_id='o1', text=text, supporting_chunk_ids=[chunk.pk])])
    support = check_claims(answer, [evidence_dict(chunk)])
    item = support['claims'][0]
    status = {'supported': 'entailed', 'partial': 'partial', 'unsupported': 'not_entailed',
              'contradicted': 'not_entailed', 'unavailable': 'unavailable'}[item['status']]
    return True, status, item['explanation']


def extract_obligations(document_id, limit=10):
    if not 1 <= limit <= 50:
        raise ValueError('Choose a batch size from 1 to 50.')
    doc = Document.objects.get(pk=document_id)
    if not eligible_source(doc):
        raise ValueError('Choose an in-force binding regulation, master direction or circular. Reports and consultations cannot supply binding obligations.')
    root = Path(settings.VECTORSTORE_DIR)
    root.mkdir(parents=True, exist_ok=True)
    with FileLock(str(root / f'.extract-{doc.pk}.lock'), timeout=1):
        with corpus_lock():
            VectorStore()
        complete = set(doc.extraction_records.filter(status='done', prompt_version=EXTRACTION_VERSION).values_list('content_sha256', flat=True))
        chunks = list(doc.chunks.exclude(content_sha256__in=complete).select_related('document').order_by('chunk_index')[:limit])
        counts = dict(processed=0, obligations=0, errors=0)
        for chunk in chunks:
            record, _ = ObligationExtractionRecord.objects.get_or_create(document=doc,
                content_sha256=chunk.content_sha256, prompt_version=EXTRACTION_VERSION,
                defaults=dict(chunk=chunk, status='error'))
            try:
                result, meta = structured_call(UNTRUSTED + ''' Extract zero or more explicit duties from this
binding regulatory passage. Do not infer duties from descriptions, examples or recommendations.
Preserve the obligated party, conditions and deadlines. source_quote must be verbatim.
An empty obligations array is valid. Confidence is an extraction hint, not a probability.''',
                    {'source': evidence_dict(chunk)}, Extraction)
                candidates = []
                for item in result.obligations:
                    # Validate the whole structured duty, including conditions and timing.
                    statement = ' '.join(getattr(item, field) for field in FIELDS if getattr(item, field))
                    quoted, status, explanation = check_obligation(statement, item.source_quote, chunk)
                    candidates.append(Obligation(source_document=doc, source_chunk=chunk,
                        source_paragraph_id=chunk.paragraph_id, source_content_sha256=chunk.content_sha256,
                        source_start_page=chunk.start_page, source_end_page=chunk.end_page,
                        source_printed_pages=chunk.printed_span, source_quote=item.source_quote,
                        quote_verified=quoted, **{field: getattr(item, field) for field in FIELDS},
                        extraction_confidence=item.confidence, extraction_model=meta['model'],
                        prompt_version=EXTRACTION_VERSION, entailment_status=status,
                        entailment_explanation=explanation, original_values=item.model_dump()))
                with transaction.atomic():
                    if not Chunk.objects.filter(pk=chunk.pk, content_sha256=chunk.content_sha256).exists():
                        raise ValueError('Source changed during extraction.')
                    Obligation.objects.bulk_create(candidates)
                    record.status, record.error, record.obligation_count = 'done', '', len(candidates)
                    record.model_name, record.chunk = meta['model'], chunk
                    record.save()
                counts['obligations'] += len(candidates)
            except Exception as exc:
                record.status, record.error = 'error', type(exc).__name__
                record.save(update_fields=['status', 'error', 'updated_at'])
                counts['errors'] += 1
            counts['processed'] += 1
        return counts


def review_obligation(obligation, user, action, values=None, notes=''):
    if action not in ('confirm', 'edit', 'reject'):
        raise ValueError('Unknown review action.')
    if action != 'reject':
        chunk = source_current(obligation)
        if chunk is None:
            raise ValueError('The current binding source could not be resolved. Re-extract before approval.')
        if action == 'edit':
            for key in FIELDS:
                setattr(obligation, key, (values or {}).get(key, getattr(obligation, key)))
        statement = ' '.join(getattr(obligation, field) for field in FIELDS if getattr(obligation, field))
        quoted, status, explanation = check_obligation(statement, obligation.source_quote, chunk)
        obligation.quote_verified, obligation.entailment_status = quoted, status
        obligation.entailment_explanation = explanation
        if not quoted or status != 'entailed':
            obligation.review_status = 'pending'
            obligation.reviewer = obligation.reviewed_at = None
            obligation.save()
            raise ValueError('Source support is not established. The obligation remains pending review.')
        obligation.source_chunk = chunk
    obligation.review_status = {'confirm': 'confirmed', 'edit': 'edited', 'reject': 'rejected'}[action]
    obligation.reviewer, obligation.reviewed_at, obligation.reviewer_notes = user, timezone.now(), notes
    obligation.full_clean()
    obligation.save()
    return obligation
