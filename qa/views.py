"""
Views for the Compliance Q&A application.

Handles the main question-answering interface, document management,
query logging, and evaluation dashboard.
"""
import time
import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings

from .models import Document, Chunk, QueryLog, GoldQuestion, EvalRun, EvalResult
from .forms import QuestionForm, DocumentUploadForm

logger = logging.getLogger(__name__)


def index(request):
    """Home page with system stats and quick-ask form."""
    stats = {
        'total_documents': Document.objects.count(),
        'indexed_documents': Document.objects.filter(is_indexed=True).count(),
        'total_chunks': Chunk.objects.count(),
        'total_queries': QueryLog.objects.count(),
    }
    return render(request, 'qa/index.html', {'stats': stats})


@login_required
def ask_question(request):
    """Handle question submission and display RAG-powered answers."""
    context = {
        'answer': None,
        'question': '',
        'chunks': [],
        'citation_check': None,
        'not_found': False,
    }

    # Handle GET with pre-filled question (from example links)
    if request.method == 'GET' and 'q' in request.GET:
        context['question'] = request.GET['q']

    if request.method == 'POST':
        question = request.POST.get('question', '').strip()
        context['question'] = question

        if not question:
            messages.warning(request, 'Please enter a question.')
            return render(request, 'qa/ask.html', context)

        # Check if there are any indexed documents
        if not Document.objects.filter(is_indexed=True).exists():
            messages.warning(
                request,
                'No documents have been indexed yet. Please upload and index '
                'a regulatory document first.'
            )
            return render(request, 'qa/ask.html', context)

        start_time = time.time()

        try:
            from rag.pipeline import answer_question as rag_answer

            vector_store_dir = str(settings.VECTORSTORE_DIR)
            api_key = settings.OPENROUTER_API_KEY

            if not api_key:
                messages.error(
                    request,
                    'OpenRouter API key is not configured. Please set OPENROUTER_API_KEY '
                    'in your .env file.'
                )
                return render(request, 'qa/ask.html', context)

            result = rag_answer(
                question=question,
                vector_store_dir=vector_store_dir,
                api_key=api_key,
                top_k=settings.RAG_TOP_K,
                threshold=settings.RAG_CONFIDENCE_THRESHOLD,
            )

            elapsed_ms = int((time.time() - start_time) * 1000)

            context['answer'] = result['answer']
            context['chunks'] = result['chunks']
            context['citation_check'] = result['citation_check']
            context['not_found'] = result['not_found']

            # Log the query
            QueryLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                question=question,
                answer=result['answer'],
                retrieved_chunk_ids=[c['chunk_id'] for c in result['chunks']],
                confidence_scores=[s['score'] for s in result.get('retrieval_scores', [])],
                citation_verified=result.get('citation_check', {}).get('verified', False),
                flagged=not result.get('citation_check', {}).get('verified', True),
                not_found=result['not_found'],
                response_time_ms=elapsed_ms,
            )

        except Exception as e:
            logger.exception('Error processing question')
            messages.error(request, f'Error processing your question: {str(e)}')

    return render(request, 'qa/ask.html', context)


@login_required
def document_list(request):
    """List all uploaded regulatory documents."""
    documents = Document.objects.all()
    return render(request, 'qa/document_list.html', {'documents': documents})


@login_required
def document_upload(request):
    """Upload a new regulatory PDF document."""
    if request.method == 'POST':
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save()
            messages.success(
                request,
                f'Document "{doc.title}" uploaded successfully. '
                f'Click "Index" to parse and vectorize it.'
            )
            return redirect('qa:document_list')
    else:
        form = DocumentUploadForm()

    return render(request, 'qa/document_upload.html', {'form': form})


@login_required
def index_document(request, pk):
    """Parse a PDF document into chunks and index them in the vector store."""
    doc = get_object_or_404(Document, pk=pk)

    if request.method != 'POST':
        return redirect('qa:document_list')

    try:
        from rag.chunker import chunk_pdf
        from rag.pipeline import index_document as rag_index_document

        # Step 1: Parse PDF into chunks
        pdf_path = doc.file.path
        raw_chunks = chunk_pdf(pdf_path, document_title=doc.title)

        if not raw_chunks:
            messages.warning(request, f'No chunks could be extracted from "{doc.title}".')
            return redirect('qa:document_list')

        # Step 2: Save chunks to database
        # Clear any existing chunks first
        doc.chunks.all().delete()

        for chunk_data in raw_chunks:
            Chunk.objects.create(
                document=doc,
                chunk_index=chunk_data['chunk_index'],
                paragraph_id=chunk_data.get('paragraph_id', ''),
                text=chunk_data['text'],
                page_number=chunk_data.get('page_number'),
                metadata=chunk_data.get('metadata', {}),
            )

        # Step 3: Index chunks in vector store
        vector_store_dir = str(settings.VECTORSTORE_DIR)
        num_indexed = rag_index_document(doc.id, vector_store_dir)

        # Step 4: Update document status
        doc.is_indexed = True
        doc.total_chunks = num_indexed
        doc.save()

        messages.success(
            request,
            f'Successfully indexed "{doc.title}": {num_indexed} chunks parsed and vectorized.'
        )

    except Exception as e:
        logger.exception(f'Error indexing document {doc.id}')
        messages.error(request, f'Error indexing document: {str(e)}')

    return redirect('qa:document_list')


@login_required
def delete_document(request, pk):
    """Delete a document and its chunks, removing them from the vector store."""
    doc = get_object_or_404(Document, pk=pk)

    if request.method != 'POST':
        return redirect('qa:document_list')

    try:
        # Remove chunks from vector store
        if doc.is_indexed:
            from rag.vectorstore import VectorStore

            chunk_ids = list(doc.chunks.values_list('id', flat=True))
            if chunk_ids:
                vector_store_dir = str(settings.VECTORSTORE_DIR)
                vs = VectorStore(vector_store_dir)
                vs.remove_document_chunks(chunk_ids)
                vs.save()

        title = doc.title
        doc.delete()
        messages.success(request, f'Document "{title}" deleted successfully.')

    except Exception as e:
        logger.exception(f'Error deleting document {doc.id}')
        messages.error(request, f'Error deleting document: {str(e)}')

    return redirect('qa:document_list')


@login_required
def query_log(request):
    """Display the audit log of all queries."""
    queries = QueryLog.objects.select_related('user').all()[:100]
    return render(request, 'qa/query_log.html', {'queries': queries})


@login_required
def eval_dashboard(request):
    """Display the evaluation dashboard with run history."""
    eval_runs = EvalRun.objects.all().order_by('-run_at')[:20]
    latest_run = eval_runs[0] if eval_runs else None
    latest_results = []

    if latest_run:
        latest_results = EvalResult.objects.filter(
            eval_run=latest_run
        ).select_related('gold_question').all()

    context = {
        'eval_runs': eval_runs,
        'latest_run': latest_run,
        'latest_results': latest_results,
        'gold_count': GoldQuestion.objects.count(),
    }
    return render(request, 'qa/eval_dashboard.html', context)


@login_required
def run_eval(request):
    """Run evaluation against all gold-standard questions."""
    if request.method != 'POST':
        return redirect('qa:eval_dashboard')

    gold_questions = GoldQuestion.objects.all()

    if not gold_questions.exists():
        messages.warning(
            request,
            'No gold-standard questions found. Add them via the admin panel first.'
        )
        return redirect('qa:eval_dashboard')

    if not Document.objects.filter(is_indexed=True).exists():
        messages.warning(request, 'No indexed documents. Index a document first.')
        return redirect('qa:eval_dashboard')

    try:
        from rag.pipeline import answer_question as rag_answer

        vector_store_dir = str(settings.VECTORSTORE_DIR)
        api_key = settings.OPENROUTER_API_KEY

        if not api_key:
            messages.error(request, 'OpenRouter API key not configured.')
            return redirect('qa:eval_dashboard')

        eval_run = EvalRun.objects.create(total_questions=gold_questions.count())

        correct_retrievals = 0
        correct_refusals = 0
        false_answers = 0
        total_time = 0

        for gq in gold_questions:
            start_time = time.time()

            try:
                result = rag_answer(
                    question=gq.question,
                    vector_store_dir=vector_store_dir,
                    api_key=api_key,
                    top_k=settings.RAG_TOP_K,
                    threshold=settings.RAG_CONFIDENCE_THRESHOLD,
                )
                elapsed_ms = int((time.time() - start_time) * 1000)
                total_time += elapsed_ms

                # Determine answer quality
                retrieved_ids = [c.get('paragraph_id', '') for c in result['chunks']]

                if gq.category == 'unanswerable':
                    if result['not_found']:
                        quality = 'refused'
                        correct_refusals += 1
                    else:
                        quality = 'wrong'
                        false_answers += 1
                else:
                    if result['not_found']:
                        quality = 'false_refuse'
                        false_answers += 1
                    else:
                        # Check if expected paragraphs were retrieved
                        expected_ids = set(gq.expected_paragraph_ids) if gq.expected_paragraph_ids else set()
                        if expected_ids and expected_ids.issubset(set(retrieved_ids)):
                            quality = 'correct'
                            correct_retrievals += 1
                        elif expected_ids and any(eid in retrieved_ids for eid in expected_ids):
                            quality = 'partial'
                            correct_retrievals += 1  # Count partial as correct for accuracy
                        else:
                            quality = 'correct' if not expected_ids else 'wrong'
                            if not expected_ids:
                                correct_retrievals += 1
                            else:
                                false_answers += 1

                # Check retrieval correctness
                retrieval_correct = False
                if gq.expected_paragraph_ids:
                    expected = set(gq.expected_paragraph_ids)
                    retrieval_correct = expected.issubset(set(retrieved_ids))
                elif result['not_found'] and gq.category == 'unanswerable':
                    retrieval_correct = True

                EvalResult.objects.create(
                    eval_run=eval_run,
                    gold_question=gq,
                    system_answer=result['answer'],
                    retrieved_chunk_ids=[c.get('chunk_id') for c in result['chunks']],
                    retrieval_correct=retrieval_correct,
                    answer_quality=quality,
                    response_time_ms=elapsed_ms,
                )

            except Exception as e:
                logger.exception(f'Error evaluating gold question {gq.id}')
                elapsed_ms = int((time.time() - start_time) * 1000)
                total_time += elapsed_ms
                false_answers += 1

                EvalResult.objects.create(
                    eval_run=eval_run,
                    gold_question=gq,
                    system_answer=f'Error: {str(e)}',
                    answer_quality='wrong',
                    response_time_ms=elapsed_ms,
                )

        # Update eval run summary
        eval_run.correct_retrievals = correct_retrievals
        eval_run.correct_refusals = correct_refusals
        eval_run.false_answers = false_answers
        eval_run.avg_response_time_ms = total_time / gold_questions.count() if gold_questions.count() > 0 else 0
        eval_run.save()

        messages.success(
            request,
            f'Evaluation complete: {eval_run.accuracy():.1f}% accuracy '
            f'({correct_retrievals} correct, {correct_refusals} correct refusals, '
            f'{false_answers} errors)'
        )

    except Exception as e:
        logger.exception('Error running evaluation')
        messages.error(request, f'Error running evaluation: {str(e)}')

    return redirect('qa:eval_dashboard')
