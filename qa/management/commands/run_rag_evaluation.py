from django.core.management.base import BaseCommand, CommandError
from qa.services.evaluation import run_evaluation


class Command(BaseCommand):
    help = 'Evaluate a reviewed, source-aligned question split using separate metrics.'

    def add_arguments(self, parser):
        parser.add_argument('--label', default='evaluation')
        parser.add_argument('--split', choices=['dev', 'test'], default='test')
        parser.add_argument('--mode', choices=['dense', 'hybrid', 'hybrid_rerank'], default='dense')
        parser.add_argument('--allow-unreviewed', action='store_true', help='Explicitly mark results provisional; never approve gold questions.')
        parser.add_argument('--retrieval-only', action='store_true', help='Measure retrieval without model-provider calls.')

    def handle(self, label, split, mode, allow_unreviewed, retrieval_only, **options):
        try:
            run = run_evaluation(label, split, mode, allow_unreviewed, retrieval_only)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f'Evaluation {run.pk}: {run.status}; see the dashboard for metric coverage.')
