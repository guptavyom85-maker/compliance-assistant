from django.core.management.base import BaseCommand, CommandError
from qa.services.obligations import extract_obligations


class Command(BaseCommand):
    help = 'Extract a resumable batch of obligations; every candidate requires human review.'
    def add_arguments(self, parser):
        parser.add_argument('--document-id', type=int, required=True)
        parser.add_argument('--limit', type=int, default=10)
    def handle(self, document_id, limit, **options):
        try:
            counts = extract_obligations(document_id, limit)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(str(counts))
