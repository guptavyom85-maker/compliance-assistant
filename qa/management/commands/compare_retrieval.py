import json
from django.core.management.base import BaseCommand, CommandError
from qa.services.evaluation import run_evaluation


class Command(BaseCommand):
    help = 'Run dense/hybrid/reranked retrieval on the same split without answer-provider calls.'
    def add_arguments(self, parser):
        parser.add_argument('--split', choices=['dev', 'test'], default='test')
        parser.add_argument('--allow-unreviewed', action='store_true')
    def handle(self, split, allow_unreviewed, **options):
        rows, fingerprint = [], None
        for mode in ('dense', 'hybrid', 'hybrid_rerank'):
            self.stdout.write(f'Running {mode}...', ending='\n')
            try:
                run = run_evaluation(f'{mode}-comparison', split, mode, allow_unreviewed, retrieval_only=True)
            except Exception as exc:
                raise CommandError(f'{mode} failed: {type(exc).__name__}') from exc
            current = run.configuration['corpus_fingerprint']
            if fingerprint and fingerprint != current:
                raise CommandError('Corpus changed between experiments; results are not comparable.')
            fingerprint = current
            rows.append(dict(run=run.pk, mode=mode, status=run.status, hit1=run.retrieval_hit_at_1,
                hit3=run.retrieval_hit_at_3, hit5=run.retrieval_hit_at_k, recall5=run.retrieval_recall_at_k,
                mrr=run.retrieval_mrr, median_ms=run.median_latency_ms, p95_ms=run.p95_latency_ms,
                errors=run.configuration['coverage']['errors']))
            self.stdout.write(json.dumps(rows[-1]))
        self.stdout.write('Provisional: ' + str(allow_unreviewed) + '. No gold approvals or answer-quality claims were created.')
