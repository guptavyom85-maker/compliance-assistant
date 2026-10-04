from collections import Counter
from statistics import median
import math
import re
from django.utils.dateparse import parse_date
from qa.models import QueryLog, Obligation, GapFinding, Document, EvalRun


def summarize(start=None, end=None):
    queries = QueryLog.objects.all()
    for supplied in (start, end):
        if supplied and parse_date(supplied) is None:
            raise ValueError('Use YYYY-MM-DD dates.')
    if start:
        queries = queries.filter(created_at__date__gte=parse_date(start))
    if end:
        queries = queries.filter(created_at__date__lte=parse_date(end))
    rows = list(queries)
    timings = sorted(q.response_time_ms for q in rows if q.response_time_ms is not None)
    # Transparent tags; these are keyword frequencies, not inferred topic accuracy.
    tags = Counter()
    for q in rows:
        for tag, words in {'lending': ['loan', 'lending', 'borrower'], 'derivatives': ['derivative', 'option', 'expiry'],
                           'banking': ['bank', 'deposit', 'scb'], 'policy': ['policy', 'obligation', 'compliance']}.items():
            if any(word in q.question.lower() for word in words):
                tags[tag] += 1
    judged = [q.faithfulness_score for q in rows if q.faithfulness_score is not None]
    costs = [q.estimated_cost for q in rows if q.estimated_cost is not None]
    return dict(total=len(rows), errors=sum(bool(q.error) for q in rows),
        refusal_rate=sum(q.not_found for q in rows) / len(rows) if rows else None,
        confidence=dict(Counter(q.confidence_band or 'unmeasured' for q in rows)),
        faithfulness=sum(judged) / len(judged) if judged else None, support_measured=len(judged),
        topics=dict(tags), median_ms=median(timings) if timings else None,
        p95_ms=timings[math.ceil(.95 * len(timings)) - 1] if timings else None,
        known_cost=sum(costs) if costs else None, cost_measured=len(costs),
        open_answers=QueryLog.objects.filter(review_required=True, review_status='open').count(),
        pending_obligations=Obligation.objects.filter(review_status='pending').count(),
        pending_findings=GapFinding.objects.filter(review_status='pending').count(),
        index_errors=Document.objects.filter(index_status='error').count(),
        latest_labeled_eval=EvalRun.objects.exclude(configuration={}).order_by('-run_at').first())
