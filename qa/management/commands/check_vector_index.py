import json
from django.core.management.base import BaseCommand, CommandError
from rag.vectorstore import VectorStore, corpus_lock, IndexIntegrityError


class Command(BaseCommand):
    help = 'Validate active generation against configuration and the current corpus.'

    def handle(self, **options):
        try:
            with corpus_lock():
                manifest = VectorStore().manifest
        except IndexIntegrityError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(manifest, indent=2))
