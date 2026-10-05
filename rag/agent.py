"""Bounded evidence-gathering plan with persisted operational trace.

Workers are processes so a timed-out inference/tool step can be terminated,
not merely abandoned in a thread that continues spending resources.
"""
import json
import multiprocessing
import time
from typing import Literal
from django.conf import settings
from django.utils import timezone
from pydantic import Field
from .schemas import StrictModel
from .generator import structured_call, GenerationError
from .prompts import UNTRUSTED

PLAN_VERSION = 'plan-1'


class ToolStep(StrictModel):
    tool: Literal['search_documents', 'get_document_metadata', 'get_chunks', 'compare_documents']
    arguments: dict


class Plan(StrictModel):
    summary: str = Field(max_length=1000)
    sub_questions: list[str] = Field(min_length=1, max_length=4)
    steps: list[ToolStep] = Field(min_length=1, max_length=6)


def needs_agent(question):
    text = question.lower()
    return any(word in text for word in ('compare', 'difference between', 'what changed', 'versus', ' vs ', 'and how', 'and which'))


def _worker(connection, kind, data):
    try:
        import os
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'compliance_assistant.settings')
        import django
        django.setup()
        if kind == 'plan':
            prompt = UNTRUSTED + ''' Produce a short evidence-gathering plan, not hidden reasoning.
Use only these tools: search_documents(query,document_ids,top_k),
get_document_metadata(document_ids), get_chunks(chunk_ids),
compare_documents(document_a,document_b,topic). Only use known document/chunk IDs.
Use document metadata to select relevant versions. No more than four subquestions
and six tool calls. For a change-over-time question, search both versions explicitly.
Arguments must be plain JSON with the indicated names. No code or external tools.'''
            value, meta = structured_call(prompt, data, Plan)
            result = {'plan': value.model_dump(), 'metadata': meta}
        elif kind == 'synthesize':
            from .schemas import Answer
            from .prompts import ANSWER
            from .faithfulness import check_claims
            answer, metadata = structured_call(ANSWER, data, Answer)
            support = check_claims(answer, data['passages'])
            result = {'answer': answer.model_dump(), 'metadata': metadata, 'support': support}
        else:
            from .tools import execute
            from .retriever import search_documents
            from functools import partial
            result = execute(data['tool'], data['arguments'], partial(search_documents,
                mode=data.get('retrieval_mode'), document_type=None), data.get('allowed_document_ids'))
        connection.send({'ok': True, 'result': json.loads(json.dumps(result, default=str))})
    except Exception as exc:
        connection.send({'ok': False, 'error': type(exc).__name__})
    finally:
        connection.close()


def bounded_call(kind, data, seconds):
    if seconds <= 0:
        raise TimeoutError('Agent time budget exhausted.')
    context = multiprocessing.get_context('spawn')
    reader, writer = context.Pipe(duplex=False)
    process = context.Process(target=_worker, args=(writer, kind, data), daemon=True)
    process.start()
    writer.close()
    try:
        if not reader.poll(seconds):
            raise TimeoutError('Agent step timed out.')
        result = reader.recv()
        if not result['ok']:
            raise GenerationError('Agent operation failed: ' + result['error'])
        return result['result']
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=3)
        reader.close()


def gather(question, user=None, mode=None, document_ids=None):
    from qa.models import AgentRun, AgentStep, Document
    run = AgentRun.objects.create(user=user, question=question)
    started = time.monotonic()
    def remaining():
        return min(settings.RAG_AGENT_STEP_TIMEOUT_SECONDS,
                   settings.RAG_AGENT_TOTAL_TIMEOUT_SECONDS - (time.monotonic() - started))
    try:
        documents = Document.objects.filter(chunks__isnull=False).distinct()
        if document_ids is None:
            documents = documents.filter(document_type='regulation')
        else:
            documents = documents.filter(pk__in=document_ids)
        catalog = list(documents.values('id', 'title', 'document_type', 'version_label',
            'version_family', 'source_category', 'status', 'effective_date', 'publication_date'))
        if not catalog:
            raise ValueError('No searchable documents are available in the selected scope.')
        # Do not pretend unrelated sources are historical versions of one rule.
        if any(term in question.lower() for term in ('what changed', 'amendment', 'previous version')):
            dated = [d for d in catalog if d['version_family'] and d['version_label'] and (d['effective_date'] or d['publication_date'])]
            families = {d['version_family'] for d in dated if sum(other['version_family'] == d['version_family'] for other in dated) >= 2}
            if len(families) != 1:
                raise ValueError('A change-over-time question requires two dated source versions.')
            catalog = [d for d in dated if d['version_family'] in families]
        raw = bounded_call('plan', {'question': question, 'documents': catalog}, remaining())
        plan = Plan.model_validate(raw['plan'])
        if len(plan.steps) > settings.RAG_MAX_AGENT_STEPS or len(plan.sub_questions) > settings.RAG_MAX_AGENT_SUBQUESTIONS:
            raise ValueError('Plan exceeds configured bounds.')
        run.plan_summary, run.sub_questions = plan.summary, plan.sub_questions
        run.save()
        AgentStep.objects.create(run=run, position=0, step_type='plan', output_summary=plan.summary,
            tool_input={'prompt_version': PLAN_VERSION, 'model': raw.get('metadata', {}).get('model', '')})
        chunks = {}
        for position, step in enumerate(plan.steps, 1):
            allowed_ids = {d['id'] for d in catalog}
            referenced = set(step.arguments.get('document_ids', []))
            referenced.update(step.arguments[k] for k in ('document_a', 'document_b') if k in step.arguments)
            if not referenced.issubset(allowed_ids):
                raise ValueError('Plan references a document outside the approved catalog.')
            if step.tool == 'search_documents' and not step.arguments.get('document_ids'):
                step.arguments['document_ids'] = sorted(allowed_ids)
            step_start = time.monotonic()
            entry = AgentStep.objects.create(run=run, position=position, step_type='tool',
                tool_name=step.tool, tool_input=step.arguments)
            try:
                result = bounded_call('tool', dict(**step.model_dump(),
                    retrieval_mode=mode or settings.RAG_RETRIEVAL_MODE,
                    allowed_document_ids=sorted(allowed_ids)), remaining())
                for row in result:
                    if 'chunk_id' in row:
                        chunks[row['chunk_id']] = row
                entry.evidence_chunk_ids = [r['chunk_id'] for r in result if 'chunk_id' in r]
                entry.output_summary = json.dumps(result, ensure_ascii=False, default=str)[:12000]
            except Exception as exc:
                entry.error = type(exc).__name__
                raise
            finally:
                entry.latency_ms = round((time.monotonic() - step_start) * 1000)
                entry.save()
                run.step_count = position
                run.save(update_fields=['step_count'])
        if any(c['document_id'] not in {d['id'] for d in catalog} for c in chunks.values()):
            raise ValueError('Evidence is outside the selected document scope.')
        return run, list(chunks.values())[:20]
    except Exception as exc:
        run.status, run.error, run.finished_at = 'abstained', type(exc).__name__, timezone.now()
        run.save()
        AgentStep.objects.create(run=run, position=run.step_count + 1, step_type='decision',
            output_summary='Insufficient evidence or bounded execution failed. Human review is required.', error=run.error)
        return run, []
