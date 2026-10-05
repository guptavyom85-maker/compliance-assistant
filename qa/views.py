import logging
import time
import traceback
from pathlib import Path
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import Document, Chunk, QueryLog, GoldQuestion, GoldEvidence, EvalRun
from .forms import QuestionForm, DocumentUploadForm
from .permissions import require_perm, can_view_query
from .services import documents
from .services.evaluation import run_evaluation, validate_gold, matching_chunks
from rag.vectorstore import VectorStore, IndexIntegrityError, corpus_lock
from rag.generator import GenerationError

logger = logging.getLogger(__name__)

def index(request):
    # Do not disclose private corpus/query counts to anonymous visitors.
    stats = dict(total_documents=0, indexed_documents=0, total_chunks=0, total_queries=0)
    if request.user.is_authenticated:
        stats.update(total_documents=Document.objects.count(),
                     indexed_documents=Document.objects.filter(is_indexed=True).count(),
                     total_chunks=Chunk.objects.count(), total_queries=QueryLog.objects.filter(user=request.user).count())
    return render(request, 'qa/index.html', {'stats': stats})

@require_perm()
def ask_question(request):
    form = QuestionForm(request.POST or None, initial={'question': request.GET.get('q', '')})
    if request.method == 'POST' and form.is_valid():
        from rag.pipeline import answer_question
        started = time.monotonic()
        try:
            from rag.agent import needs_agent
            strategy = form.cleaned_data.get('strategy') or 'auto'
            document_ids = list(form.cleaned_data['documents'].values_list('pk', flat=True))
            result = answer_question(form.cleaned_data['question'],
                mode=form.cleaned_data.get('retrieval') or settings.RAG_RETRIEVAL_MODE,
                use_agent=strategy == 'agent' or (strategy == 'auto' and needs_agent(form.cleaned_data['question'])),
                user=request.user, document_ids=document_ids)
            payload = result['answer_payload']
            log = QueryLog.objects.create(user=request.user, question=form.cleaned_data['question'],
                answer=result['answer'], answer_payload=payload, not_found=result['not_found'],
                retrieved_chunk_ids=[c['chunk_id'] for c in result['chunks']],
                confidence_scores=[c.get('score', 0) for c in result['chunks']],
                citation_verified=result['citation_check']['verified'], flagged=payload['requires_human_review'],
                model_name=result['model_name'], prompt_version=result['prompt_version'],
                retrieval_config=result['retrieval_config'], faithfulness_score=result['faithfulness_score'],
                citation_precision=result['citation_precision'], confidence_band=payload['confidence_band'],
                review_required=payload['requires_human_review'], review_reason=payload['review_reason'],
                response_time_ms=round((time.monotonic() - started) * 1000))
            if result.get('agent_run_id'):
                from .models import AgentRun
                AgentRun.objects.filter(pk=result['agent_run_id']).update(query_log=log)
                log.agent_used = True
                log.save(update_fields=['agent_used'])
            return redirect('qa:answer_detail', pk=log.pk)
        except Exception as exc:
            # Record only frames and exception class. Exception messages/chains
            # can contain provider response bodies or private validation inputs.
            logger.error('Question processing failed (%s).\n%s', type(exc).__name__,
                         ''.join(traceback.format_list(traceback.extract_tb(exc.__traceback__))))
            failed = QueryLog.objects.create(user=request.user, question=form.cleaned_data['question'],
                error=type(exc).__name__, review_required=True, review_reason='Processing failed.',
                retrieval_config={'document_ids': document_ids,
                                  'mode': form.cleaned_data.get('retrieval') or settings.RAG_RETRIEVAL_MODE,
                                  'strategy': strategy},
                response_time_ms=round((time.monotonic() - started) * 1000))
            if isinstance(exc, IndexIntegrityError):
                message = str(exc)
            elif isinstance(exc, GenerationError):
                message = 'The answer service could not return a complete response. Please retry; your question and selected documents are preserved.'
            else:
                message = 'Question processing failed. The diagnostic details have been recorded for investigation.'
            messages.error(request, f'{message} Reference: {failed.pk}.')
    return render(request, 'qa/ask.html', {'form': form})

@require_perm()
def answer_detail(request, pk):
    log = get_object_or_404(QueryLog, pk=pk)
    if not can_view_query(request.user, log):
        raise PermissionDenied
    return render(request, 'qa/answer_detail.html', {'query': log})

@require_perm()
def document_list(request):
    return render(request, 'qa/document_list.html', {'documents': Document.objects.all()})

@require_perm('qa.upload_document')
def document_upload(request):
    form = DocumentUploadForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        doc = form.save(commit=False)
        doc.uploaded_by = request.user
        doc.save()
        messages.success(request, 'Document uploaded. Index it to make its passages searchable.')
        return redirect('qa:document_list')
    return render(request, 'qa/document_upload.html', {'form': form})

@require_perm('qa.index_document')
@require_POST
def index_document(request, pk):
    get_object_or_404(Document, pk=pk)
    try:
        count = documents.index_document(pk)
        messages.success(request, f'Index activated with {count} passages from this document.')
    except Exception:
        messages.error(request, 'Indexing failed. Check the document and rebuild the index before querying.')
    return redirect('qa:document_list')

@require_perm('qa.delete_document')
@require_POST
def delete_document(request, pk):
    get_object_or_404(Document, pk=pk)
    try:
        documents.delete_document(pk)
        messages.success(request, 'Document removed from the corpus and index rebuilt. Uploaded bytes retained for recovery.')
    except Exception:
        messages.error(request, 'Deletion or rebuilding failed. Check the document list and rebuild the index before querying.')
    return redirect('qa:document_list')

@require_perm()
def document_file(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    return FileResponse(doc.file.open('rb'), content_type='application/pdf', as_attachment=False,
                        filename=Path(doc.file.name).name)

@require_perm()
def query_log(request):
    logs = QueryLog.objects.select_related('user')
    if not request.user.has_perm('qa.view_global_logs'):
        logs = logs.filter(user=request.user)
    return render(request, 'qa/query_log.html', {'queries': logs[:100]})

@require_perm('qa.run_evaluation')
def eval_dashboard(request):
    runs = EvalRun.objects.order_by('-run_at')[:20]
    return render(request, 'qa/eval_dashboard.html', {'runs': runs,
        'gold_errors': validate_gold(list(GoldQuestion.objects.filter(is_active=True))),
        'questions': GoldQuestion.objects.filter(is_active=True).order_by('split', 'id')})

@require_perm('qa.run_evaluation')
@require_POST
def run_eval(request):
    split = request.POST.get('split', 'test')
    if split not in ('dev', 'test'):
        messages.error(request, 'Choose development or held-out test.')
    else:
        try:
            mode = request.POST.get('mode', 'dense')
            if mode not in ('dense', 'hybrid', 'hybrid_rerank'):
                raise ValueError('Choose a supported retrieval mode.')
            run = run_evaluation(request.POST.get('label', 'web-evaluation')[:100], split, mode,
                allow_unreviewed=request.POST.get('provisional') == 'on',
                retrieval_only=request.POST.get('retrieval_only') == 'on')
            messages.success(request, f'Evaluation {run.pk}: {run.status}. Unavailable metrics are not passing scores.')
        except ValueError as exc:
            messages.error(request, str(exc))
        except Exception:
            messages.error(request, 'Evaluation failed. Check model and index configuration.')
    return redirect('qa:eval_dashboard')

@require_perm('qa.run_evaluation')
def gold_review(request, pk):
    q = get_object_or_404(GoldQuestion, pk=pk)
    error = ''
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'confirm':
            evidence = list(q.evidence.filter(required=True))
            if q.is_answerable and (not q.expected_answer.strip() or not evidence):
                error = 'Add a reference answer and required evidence before confirming.'
            elif any(not matching_chunks(e) for e in evidence):
                error = 'Every evidence reference must resolve to current source text.'
            else:
                q.reviewed_by, q.reviewed_at = request.user, timezone.now()
                q.save(update_fields=['reviewed_by', 'reviewed_at'])
                messages.success(request, 'Human review recorded.')
                return redirect('qa:eval_dashboard')
        elif action == 'save':
            form_fields = ('question', 'expected_answer', 'expected_answer_notes', 'gold_set_version')
            for field in form_fields:
                setattr(q, field, request.POST.get(field, getattr(q, field)))
            if request.POST.get('split') in ('dev', 'test'):
                q.split = request.POST['split']
            if request.POST.get('category') in dict(q.CATEGORY_CHOICES):
                q.category = request.POST['category']
            q.is_active = request.POST.get('is_active') == 'on'
            q.reviewed_at = q.reviewed_by = None
            try:
                q.full_clean()
                q.save()
                return redirect('qa:gold_review', pk=q.pk)
            except ValidationError as exc:
                error = '; '.join(exc.messages)
        elif action == 'add_evidence':
            try:
                chunk_id = int(request.POST.get('chunk_id', '0'))
            except ValueError:
                return HttpResponseBadRequest('Invalid passage identifier.')
            c = get_object_or_404(Chunk, pk=chunk_id)
            GoldEvidence.objects.update_or_create(gold_question=q, document=c.document, paragraph_id=c.paragraph_id,
                defaults=dict(chunk=c, text_anchor=c.text[:200], required=True))
            q.reviewed_at = q.reviewed_by = None
            q.save(update_fields=['reviewed_at', 'reviewed_by'])
            return redirect('qa:gold_review', pk=q.pk)
        elif action == 'remove_evidence':
            try:
                evidence_id = int(request.POST.get('evidence_id', '0'))
            except ValueError:
                return HttpResponseBadRequest('Invalid evidence identifier.')
            q.evidence.filter(pk=evidence_id).delete()
            q.reviewed_at = q.reviewed_by = None
            q.save(update_fields=['reviewed_at', 'reviewed_by'])
            return redirect('qa:gold_review', pk=q.pk)
        else:
            return HttpResponseBadRequest('Unknown review action.')
    passages = Chunk.objects.select_related('document').all()
    search = request.GET.get('search', '').strip()
    if search:
        passages = passages.filter(text__icontains=search)
    evidence = [(e, matching_chunks(e)) for e in q.evidence.select_related('document')]
    return render(request, 'qa/gold_review.html', dict(question=q, evidence=evidence, passages=passages[:50], search=search, error=error))

@require_perm('qa.manage_corpus')
def index_status(request):
    try:
        with corpus_lock():
            manifest = VectorStore().manifest
        error = ''
    except IndexIntegrityError as exc:
        manifest, error = {}, str(exc)
    return render(request, 'qa/index_status.html', {'manifest': manifest, 'error': error})
