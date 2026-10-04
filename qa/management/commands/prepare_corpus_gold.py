"""Create review drafts from the two existing source documents, never approvals."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from qa.models import Chunk, GoldQuestion, GoldEvidence

VERSION = 'corpus-aligned-draft-1'
# These are claims about what the supplied documents say, not current legal advice.
DRAFTS = [
    ('dev', 'direct', 'What is the stated objective of the loaded SEBI derivatives consultation paper?',
     'The paper seeks to enhance investor protection and promote market stability in derivatives while ensuring sustained capital formation.',
     ['this consultation paper seeks to introduce measures']),
    ('test', 'direct', 'According to the SEBI consultation paper, when did NSE introduce weekly options on a sectoral index and weekly contracts on the benchmark index?',
     'The paper describes introduction on a sectoral index in May 2016 and on the benchmark index in February 2019.',
     ['From introduction of weekly options contracts']),
    ('dev', 'direct', 'Who decides the expiry day of weekly options contracts according to the loaded SEBI consultation paper?',
     'Within the regulatory ambit, broad specifications including the expiry day are left to the individual exchange.',
     ['deciding the expiry day is left to individual exchange']),
    ('test', 'direct', 'What happened to the distribution of weekly expiry dates after BSE reintroduced weekly index derivatives contracts in May 2023, according to the paper?',
     'Exchanges shuffled their expiry dates, resulting in expiry of weekly index derivatives on all five trading days at the time of the paper.',
     ['expiry of weekly index derivatives contracts on all five trading days']),
    ('dev', 'direct', 'What annual growth in aggregate SCB deposits does the loaded RBI report give for 2025-26?',
     'The report states that aggregate SCB deposits grew by 11.5 per cent year on year during 2025-26.',
     ['Aggregate deposits of SCBs grew at 11.5 per cent']),
    ('test', 'direct', 'Which four categories of banks are included as SCBs for the exercise described in the RBI report excerpt?',
     'Public sector banks, private sector banks, foreign banks and small finance banks.',
     ['SCBs include public sector banks']),
    ('dev', 'multi_para', 'What does the SEBI paper report about the total number of demat accounts by May 2024 and the change in individual investors\' index-option share between FY2018 and FY2024?',
     'Demat accounts reached 15.8 crore by the end of May 2024. The paper says that for every 100 rupees traded by individual investors, the index-options share rose from 2 rupees in FY2018 to 41 rupees in FY2024.',
     ['total number of demat accounts in India rose to 15.8 crore', 'This number rose to']),
    ('test', 'multi_para', 'In the RBI report excerpt, what is the provisional data cutoff and which banks are included as SCBs?',
     'The cutoff is June 11, 2026. SCBs include public sector, private sector, foreign and small finance banks.',
     ['provisional data available as of June 11, 2026', 'SCBs include public sector banks']),
    ('dev', 'unanswerable', 'What is the internal password-reset procedure for our company compliance portal?',
     'Abstain: the supplied regulatory sources do not document the company portal procedure.', []),
    ('test', 'unanswerable', 'What is the approved travel reimbursement limit in our company policy?',
     'Abstain: no company travel policy has been supplied.', []),
]


class Command(BaseCommand):
    help = 'Create corpus-aligned gold drafts for human review; retain historic questions and runs.'

    @transaction.atomic
    def handle(self, **options):
        for split, category, question, answer, anchors in DRAFTS:
            sources = []
            for anchor in anchors:
                matches = list(Chunk.objects.filter(text__contains=anchor).select_related('document'))
                if len(matches) != 1:
                    raise CommandError(f'Anchor must resolve uniquely: {anchor!r} ({len(matches)} matches).')
                sources.append((matches[0], anchor))
            q, created = GoldQuestion.objects.get_or_create(question=question, gold_set_version=VERSION,
                defaults=dict(expected_answer=answer, category=category, split=split, is_active=True,
                    expected_answer_notes='Draft prepared from supplied corpus. Human review required; no approval has been inferred.'))
            if created or (q.reviewed_at is None and q.expected_answer == answer):
                # Refresh only untouched draft evidence after re-chunking. Never
                # overwrite a human-reviewed reference or edited reference text.
                q.evidence.all().delete()
                for c, anchor in sources:
                    # Different anchors in the same clause may resolve to one required evidence row.
                    GoldEvidence.objects.get_or_create(gold_question=q, document=c.document, paragraph_id=c.paragraph_id,
                        defaults=dict(chunk=c, text_anchor=anchor, notes='Draft source anchor.'))
            self.stdout.write(f'{q.pk}: {split}, {category}, {"created" if created else "retained"}')
        # Keep all historical evidence, question wording, and run results intact.
        retired = GoldQuestion.objects.filter(gold_set_version='v0-legacy', reviewed_at__isnull=True).update(is_active=False)
        self.stdout.write(f'{retired} unreviewed legacy questions made inactive. New questions still require human review.')
