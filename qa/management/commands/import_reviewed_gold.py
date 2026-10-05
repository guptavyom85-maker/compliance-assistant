"""Import the user-reviewed SEBI/RBI question bank with resolving evidence."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from qa.models import Chunk, Document, GoldEvidence, GoldQuestion


VERSION = 'human-reviewed-sebi-rbi-2026-10-05'

# Evidence uses file suffix + paragraph + a short extracted-text anchor so the
# import remains stable across vector-index rebuilds and changing chunk IDs.
QUESTIONS = [
    dict(split='dev', category='direct', file='SEBI_Derivatives_In_depth.pdf',
         question='What proportion of individual traders in the equity F&O segment incurred losses according to the SEBI study of January 2023?',
         answer='The said study found that 89% of individual traders in the equity F&O segment incurred losses.',
         location='Para 2.3.7, p. 6', evidence=[('2.3.7.', '89% of individual traders')]),
    dict(split='test', category='direct', file='SEBI_Derivatives_In_depth.pdf',
         question='What change is proposed for weekly options contracts offered by an exchange?',
         answer='weekly options contracts to be provided on single benchmark index of an exchange.',
         location='Para 3.6.4, p. 14', evidence=[('3.6.4.', 'weekly options contracts to be provided')]),
    dict(split='dev', category='direct', file='SEBI_Derivatives_In_depth.pdf',
         question='By how much is the Extreme Loss Margin (ELM) proposed to be increased on the day before expiry and on expiry day?',
         answer='a. At the start of the day before expiry, Extreme Loss Margin (ELM) to be increased by 3%.\nb. At the start of expiry day, ELM to be further increased by 5%.',
         location='Para 3.7.3, p. 15', evidence=[('3.7.3.', 'Extreme Loss Margin (ELM) to be increased by 3%')]),
    dict(split='test', category='multi_para', file='SEBI_Derivatives_In_depth.pdf',
         question='How is the minimum contract size for index derivatives proposed to be revised in Phase 1 and Phase 2?',
         answer='Phase 1: Minimum value of derivatives contract at the time of introduction to be between ₹15 lakhs to ₹20 lakhs.\nPhase 2: After 6 months, minimum value of derivatives contract to be between the interval of ₹20 lakhs to ₹30 lakhs',
         location='Para 3.5.3, p. 12', evidence=[
             ('3.5.3.1.', 'Phase 1: Minimum value of derivatives contract'),
             ('3.5.3.2.', 'Phase 2: After 6 months'),
         ]),
    dict(split='dev', category='direct', file='SEBI_Derivatives_In_depth.pdf',
         question='What is the proposal on the number of strikes to be introduced for an index derivatives contract at launch?',
         answer='Not more than 50 strikes to be introduced for an index derivatives contract at the time of contract launch.',
         location='Para 3.1.4.2, p. 9', evidence=[('3.1.4.2.', 'Not more than 50 strikes')]),

    dict(split='test', category='direct', file='financialstatbility_report_for_NBFC.pdf',
         question='How much did the aggregate credit growth of NBFCs (Upper and Middle Layers) decelerate to in March 2026?',
         answer='The aggregate credit growth of NBFCs (Upper and Middle Layers) decelerated to 16.6 per cent y-o-y in March 2026 (Chart 2.28 a).',
         location='Para 2.55, p. 86', evidence=[('2.55', 'aggregate credit growth of NBFCs')]),
    dict(split='dev', category='multi_para', file='financialstatbility_report_for_NBFC.pdf',
         question='What were the NII growth and PAT growth of NBFCs in March 2026?',
         answer='The NII growth y-o-y of NBFCs increased by 9.7 per cent in March 2026 (Chart 2.28f). Profitability also improved, as reflected in PAT growth of 11.8 per cent.',
         location='Para 2.56, p. 86', evidence=[
             ('2.56', 'NII growth y-o-y of NBFCs increased by'),
             ('9.7', '9.7 per cent in March 2026'),
         ]),
    dict(split='test', category='multi_para', file='financialstatbility_report_for_NBFC.pdf',
         question='What does the baseline credit-risk stress test project for the GNPA ratio of the sample NBFCs by March 2027?',
         answer='Under the baseline scenario, the system-level GNPA ratio of the sample NBFCs may rise from 2.4 per cent in March 2026 to 2.8 per cent in March 2027.',
         location='Para 2.65, p. 91', evidence=[
             ('2.65', 'baseline scenario, the system- level GNPA ratio'),
             ('2.4', '2.4 per cent in March 2026'),
             ('2027.', '2027. Consequently'),
         ]),
    dict(split='dev', category='direct', file='financialstatbility_report_for_NBFC.pdf',
         question='What would happen to system-level CRAR if the top three individual borrowers of NBFCs defaulted?',
         answer='the system level CRAR would decline by 230 bps (Chart 2.31 a) and eight NBFCs would face a situation of a drop in CRAR below the regulatory minimum of 15 per cent.',
         location='Para 2.66, p. 92', evidence=[('34', 'system level CRAR would decline by 230 bps')]),
    dict(split='test', category='multi_para', file='financialstatbility_report_for_NBFC.pdf',
         question='What was the baseline projection of the aggregate CET1 ratio of the select 46 banks by March 2028 in the macro stress test?',
         answer='The aggregate CET1 capital ratio of the select 46 banks may decline from 15.2 per cent in March 2026 to 13.9 per cent by March 2028 under the baseline scenario.',
         location='Para 2.19, p. 70', evidence=[
             ('2.19', 'aggregate CET1 capital ratio of the select 46 banks'),
             ('2026', '2026 to 13.9 per cent by March 2028'),
         ]),

    dict(split='dev', category='direct', file='2026_SEBI_Master_Circulars_.pdf',
         question='When is no compensation payable to an applicant in an IPO who failed to get allotment due to SCSB failure?',
         answer='No compensation would be payable to the applicant in case the listing price is below the issue price.',
         location='Chapter 5, para 5, p. 15', evidence=[('5.', 'No compensation would be payable')]),
    dict(split='test', category='direct', file='2026_SEBI_Master_Circulars_.pdf',
         question='By how many days was the timeline for listing of shares after public issue closure reduced?',
         answer="to reduce the time taken for listing of specified securities after the closure of public issue to 3 working days (T+3 days) as against the present requirement of 6 working days (T+6 days); 'T' being issue closing date.",
         location='Chapter 11, para 1, p. 37', evidence=[('1.', 'reduce the time taken for listing of specified securities')]),
    dict(split='dev', category='direct', file='2026_SEBI_Master_Circulars_.pdf',
         question='From which day will shares allotted pursuant to a bonus issue be available for trading?',
         answer='The shares allotted pursuant to the bonus issue shall be made available for trading on the next working date of allotment (T+2 day).',
         location='Chapter 14, para 2.6, p. 41', evidence=[('2.6.', 'shares allotted pursuant to the bonus issue')]),
    dict(split='test', category='direct', file='2026_SEBI_Master_Circulars_.pdf',
         question='What redressal window and interest penalty apply to an applicant whose application was not considered due to SCSB failure?',
         answer='Any applicant whose application has not been considered for allotment, due to failure on the part of the SCSB, shall have the option to seek redressal of the same within three months of the listing date with the concerned SCSB. On receipt of such application/s, the SCSB would be required to resolve the same within 15 days, failing which it would have to pay interest at the rate of 15% per annum for any delay beyond the said period of 15 days.',
         location='Chapter 5, para 7, p. 16', evidence=[('7.', 'option to seek redressal of the same within three months')]),
    dict(split='dev', category='direct', file='2026_SEBI_Master_Circulars_.pdf',
         question='Where is the fine realised from non-compliant listed entities credited?',
         answer='The amount of fine realized as per the above structure shall continue to be credited to the "Investor Protection Fund" of the concerned stock exchange.',
         location='Chapter 1, para 3, p. 7', evidence=[('3.', 'Investor Protection Fund')]),
]


class Command(BaseCommand):
    help = 'Replace the active gold set with the supplied human-reviewed SEBI/RBI question bank.'

    def add_arguments(self, parser):
        parser.add_argument('--reviewer', required=True, help='Existing username of the human reviewer.')

    @transaction.atomic
    def handle(self, reviewer, **options):
        try:
            reviewer_user = get_user_model().objects.get(username=reviewer)
        except get_user_model().DoesNotExist as exc:
            raise CommandError(f'Reviewer user does not exist: {reviewer}') from exc

        resolved = []
        for item in QUESTIONS:
            documents = list(Document.objects.filter(file__iendswith=item['file']))
            if len(documents) != 1:
                raise CommandError(f"Source must resolve uniquely: {item['file']} ({len(documents)} matches).")
            document = documents[0]
            evidence = []
            for paragraph_id, anchor in item['evidence']:
                chunks = list(Chunk.objects.filter(document=document, paragraph_id=paragraph_id,
                    text__icontains=anchor))
                if len(chunks) != 1:
                    raise CommandError(
                        f"Evidence must resolve uniquely: {item['file']} §{paragraph_id} / {anchor!r} "
                        f"({len(chunks)} matches)."
                    )
                evidence.append((chunks[0], anchor))
            resolved.append((item, document, evidence))

        reviewed_at = timezone.now()
        GoldQuestion.objects.exclude(gold_set_version=VERSION).filter(is_active=True).update(is_active=False)
        imported_ids = []
        for item, document, evidence in resolved:
            question, _ = GoldQuestion.objects.update_or_create(
                question=item['question'], gold_set_version=VERSION,
                defaults=dict(expected_answer=item['answer'],
                    expected_answer_notes=(
                        f"Human-reviewed question bank supplied by the user on 5 October 2026. "
                        f"Source location: {item['location']}."
                    ),
                    category=item['category'], split=item['split'], document=document,
                    is_active=True, reviewed_by=reviewer_user, reviewed_at=reviewed_at),
            )
            question.evidence.all().delete()
            for chunk, anchor in evidence:
                GoldEvidence.objects.create(gold_question=question, document=document,
                    paragraph_id=chunk.paragraph_id, text_anchor=anchor, chunk=chunk,
                    required=True, notes=f"Human-reviewed source location: {item['location']}.")
            imported_ids.append(question.pk)
            self.stdout.write(f'{question.pk}: {item["split"]} / {item["category"]} / {len(evidence)} evidence passage(s)')

        stale = GoldQuestion.objects.filter(gold_set_version=VERSION).exclude(pk__in=imported_ids)
        stale.update(is_active=False)
        self.stdout.write(self.style.SUCCESS(
            f'Activated {len(imported_ids)} human-reviewed questions; previous questions retained as inactive history.'
        ))
