from django.core.management.base import BaseCommand, CommandError
from rag.vectorstore import rebuild


class Command(BaseCommand):
    help = 'Build, validate, and atomically activate a complete index generation.'

    def handle(self, **options):
        try:
            manifest = rebuild(triggered_by='management-command')
        except Exception as exc:
            raise CommandError(f'Rebuild failed: {type(exc).__name__}. Check corpus state.') from exc
        self.stdout.write(self.style.SUCCESS(f"Generation {manifest['generation_id']}: {manifest['vector_count']} vectors"))
