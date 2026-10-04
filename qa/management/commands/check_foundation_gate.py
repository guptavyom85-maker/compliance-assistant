from django.core.management.base import BaseCommand, CommandError
from qa.models import GoldQuestion, EvalRun
from qa.services.evaluation import validate_gold
from rag.vectorstore import VectorStore, IndexIntegrityError, corpus_lock


class Command(BaseCommand):
    help = 'Report index/ground-truth/evaluation readiness. Never fabricates reviewer approval.'

    def handle(self, **options):
        errors = []
        try:
            with corpus_lock():
                m = VectorStore().manifest
            self.stdout.write(f"Index valid: {m['vector_count']} vectors")
        except IndexIntegrityError as exc:
            errors.append(str(exc))
        active = list(GoldQuestion.objects.filter(is_active=True))
        if not active:
            errors.append('No active gold questions.')
        errors.extend(validate_gold(active))
        for split in ('dev', 'test'):
            if not any(q.split == split for q in active):
                errors.append(f'No active {split} questions.')
        if not EvalRun.objects.filter(status='complete', label='dense-baseline',
                answer_correctness__isnull=False, faithfulness__isnull=False).exists():
            errors.append('A scored dense-baseline run is still required after human review.')
        if errors:
            for error in errors:
                self.stderr.write(error)
            raise CommandError('Foundation acceptance gate remains open; see docs/checkpoints/phase-0.md.')
        self.stdout.write('Data gate passes. Also verify test, deployment and human judge-validation evidence in the checkpoint.')
