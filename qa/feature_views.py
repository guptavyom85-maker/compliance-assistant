from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Document, Obligation, GapAnalysisRun, GapFinding, QueryLog, ObligationExtractionRecord, EvalResult, EvalRun
from .permissions import require_perm
from .services.obligations import extract_obligations, review_obligation, BINDING_CATEGORIES
from .services.gap_analysis import run_gap_analysis
from .services.reports import gap_pdf
from .services.analytics import summarize


class ObligationReviewForm(forms.ModelForm):
    action = forms.ChoiceField(choices=[('confirm', 'Confirm'), ('edit', 'Edit and confirm'), ('reject', 'Reject')])
    class Meta:
        model = Obligation
        fields = ['obligation_text', 'obligated_party', 'condition', 'deadline_or_trigger', 'reviewer_notes']


class GapForm(forms.Form):
    policy = forms.ModelChoiceField(queryset=Document.objects.none())
    regulations = forms.ModelMultipleChoiceField(queryset=Document.objects.none())
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['policy'].queryset = Document.objects.filter(document_type='company_policy', is_indexed=True)
        self.fields['regulations'].queryset = Document.objects.filter(document_type='regulation',
            status='in_force', source_category__in=BINDING_CATEGORIES, is_indexed=True)


@require_perm('qa.view_obligation')
def obligations(request):
    rows = Obligation.objects.select_related('source_document', 'reviewer')
    filters = {'review_status': 'status', 'source_document_id': 'document',
               'extraction_confidence': 'confidence', 'entailment_status': 'entailment', 'obligated_party__icontains': 'party'}
    for field, key in filters.items():
        value = request.GET.get(key, '').strip()
        if value and (key != 'document' or value.isdigit()):
            rows = rows.filter(**{field: value})
    return render(request, 'qa/obligation_list.html', {'obligations': rows[:200],
        'documents': Document.objects.filter(document_type='regulation'),
        'records': ObligationExtractionRecord.objects.select_related('document').order_by('-updated_at')[:20]})


@require_perm('qa.extract_obligations')
@require_POST
def extract(request, pk):
    get_object_or_404(Document, pk=pk)
    try:
        counts = extract_obligations(pk, limit=10)
        messages.success(request, f"Batch finished: {counts['processed']} passages, {counts['obligations']} candidates, {counts['errors']} errors. Run the next batch to resume.")
    except ValueError as exc:
        messages.error(request, str(exc))
    except Exception:
        messages.error(request, 'Extraction unavailable or already running; check the index/provider and retry.')
    return redirect('qa:obligations')


@require_perm('qa.review_obligation')
def obligation_review(request, pk):
    item = get_object_or_404(Obligation.objects.select_related('source_document'), pk=pk)
    form = ObligationReviewForm(request.POST or None, instance=item)
    if request.method == 'POST' and form.is_valid():
        try:
            review_obligation(item, request.user, form.cleaned_data['action'], form.cleaned_data,
                              form.cleaned_data.get('reviewer_notes', ''))
            messages.success(request, 'Review recorded.')
            return redirect('qa:obligations')
        except (ValueError, ValidationError) as exc:
            form.add_error(None, str(exc))
        except Exception:
            form.add_error(None, 'Source validation is unavailable; approval was not recorded.')
    return render(request, 'qa/obligation_review.html', {'obligation': item, 'form': form})


@require_perm('qa.run_gap_analysis')
def gap_create(request):
    form = GapForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            run = run_gap_analysis(form.cleaned_data['policy'].pk,
                list(form.cleaned_data['regulations'].values_list('pk', flat=True)), request.user)
            return redirect('qa:gap_detail', pk=run.pk)
        except ValueError as exc:
            form.add_error(None, str(exc))
        except Exception:
            form.add_error(None, 'Analysis could not start. Check the index and provider configuration.')
    runs = GapAnalysisRun.objects.select_related('policy_document')
    if not request.user.has_perm('qa.view_global_logs'):
        runs = runs.filter(created_by=request.user)
    return render(request, 'qa/gap_analysis_create.html', {'form': form, 'runs': runs[:50]})


def permitted_run(request, pk):
    run = get_object_or_404(GapAnalysisRun.objects.select_related('policy_document'), pk=pk)
    if run.created_by_id != request.user.id and not request.user.has_perm('qa.view_global_logs'):
        raise PermissionDenied
    return run


@require_perm('qa.run_gap_analysis')
def gap_detail(request, pk):
    run = permitted_run(request, pk)
    return render(request, 'qa/gap_analysis_detail.html', {'run': run, 'findings': run.findings.select_related('obligation', 'reviewer')})


@require_perm('qa.run_gap_analysis')
def gap_export(request, pk):
    run = permitted_run(request, pk)
    response = HttpResponse(gap_pdf(run), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="gap-report-{run.pk}.pdf"'
    return response


@require_perm('qa.run_gap_analysis')
@require_POST
def gap_review(request, pk):
    finding = get_object_or_404(GapFinding, pk=pk)
    permitted_run(request, finding.run_id)
    status = request.POST.get('status', '')
    if status and status not in dict(GapFinding.STATUS_CHOICES):
        return HttpResponse('Invalid status', status=400)
    if status in ('addressed', 'partially_addressed', 'conflicting') and not finding.policy_evidence:
        return HttpResponse('A matched classification requires policy evidence. Re-run with a relevant source.', status=400)
    finding.reviewer_status_override = status
    finding.review_status = 'overridden' if status else 'accepted'
    finding.reviewer, finding.reviewed_at = request.user, timezone.now()
    finding.reviewer_notes = request.POST.get('notes', '')[:4000]
    finding.save()
    from collections import Counter
    run = finding.run
    run.counts = dict(Counter(f.effective_status for f in run.findings.all()))
    run.save(update_fields=['counts'])
    return redirect('qa:gap_detail', pk=finding.run_id)


@require_perm('qa.view_global_logs')
def review_queue(request):
    return render(request, 'qa/review_queue.html', {
        'answers': QueryLog.objects.filter(review_required=True, review_status='open').select_related('user')[:100],
        'obligations': Obligation.objects.filter(review_status='pending').select_related('source_document')[:100],
        'findings': GapFinding.objects.filter(review_status='pending').select_related('run', 'obligation')[:100],
        'extractions': ObligationExtractionRecord.objects.filter(status='error', review_status='open').select_related('document')[:100],
        'documents': Document.objects.filter(index_status='error')})


@require_perm('qa.view_global_logs')
@require_POST
def resolve_review(request, kind, pk):
    state = request.POST.get('status')
    if state not in ('resolved', 'dismissed'):
        return HttpResponse('Invalid resolution', status=400)
    if kind == 'answer':
        item = get_object_or_404(QueryLog, pk=pk)
        item.review_status, item.reviewed_by, item.reviewed_at = state, request.user, timezone.now()
        item.review_notes = request.POST.get('notes', '')[:4000]
        item.save(update_fields=['review_status', 'reviewed_by', 'reviewed_at', 'review_notes'])
    elif kind == 'extraction':
        item = get_object_or_404(ObligationExtractionRecord, pk=pk)
        item.review_status = state
        item.reviewed_by, item.reviewed_at = request.user, timezone.now()
        item.review_notes = request.POST.get('notes', '')[:4000]
        item.save(update_fields=['review_status', 'reviewed_by', 'reviewed_at', 'review_notes'])
    else:
        return HttpResponse('Unknown review type', status=400)
    return redirect('qa:review_queue')


@require_perm('qa.view_global_logs')
def analytics(request):
    try:
        data = summarize(request.GET.get('start'), request.GET.get('end'))
    except ValueError as exc:
        return HttpResponse(str(exc), status=400)
    return render(request, 'qa/analytics.html', {'data': data})


def trust(request):
    return render(request, 'qa/trust.html')


@require_perm('qa.run_evaluation')
@require_POST
def judge_review(request, pk):
    from django.db import transaction
    label = request.POST.get('label')
    if label not in ('correct', 'partial', 'wrong'):
        return HttpResponse('Choose correct, partial or wrong.', status=400)
    with transaction.atomic():
        result = get_object_or_404(EvalResult, pk=pk)
        result.human_correctness_label = label
        result.save(update_fields=['human_correctness_label'])
        run = EvalRun.objects.select_for_update().get(pk=result.eval_run_id)
        history = run.configuration.setdefault('human_review_history', [])
        history.append(dict(result_id=result.pk, reviewer_id=request.user.pk,
            reviewed_at=timezone.now().isoformat(), label=label, notes=request.POST.get('notes', '')[:2000]))
        comparable = list(run.results.filter(human_correctness_label__in=['correct', 'partial', 'wrong'],
                                             correctness_label__in=['correct', 'partial', 'wrong']))
        run.configuration['judge_agreement'] = dict(count=len(comparable),
            exact_agreement=sum(r.human_correctness_label == r.correctness_label for r in comparable) / len(comparable) if comparable else None)
        run.save(update_fields=['configuration'])
    return redirect('qa:eval_dashboard')
