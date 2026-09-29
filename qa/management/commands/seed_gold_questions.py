"""
Management command to seed the database with gold-standard evaluation questions.
These are hand-written questions with known correct answers for testing the RAG system.
"""
from django.core.management.base import BaseCommand
from qa.models import GoldQuestion


GOLD_QUESTIONS = [
    {
        'question': 'What must a lender disclose to a borrower before a digital loan is executed?',
        'expected_answer': (
            'Before executing a digital loan, lenders must provide borrowers with a Key Fact Statement (KFS) '
            'containing all-inclusive cost of digital loans, annual percentage rate, recovery mechanism, '
            'details of grievance redressal officer, and cooling-off/look-up period.'
        ),
        'expected_paragraph_ids': [],
        'category': 'direct',
    },
    {
        'question': 'What are the restrictions on digital lending apps collecting data from borrowers?',
        'expected_answer': (
            'Digital lending apps can only collect data that is need-based and with prior explicit consent '
            'of the borrower. They should not access mobile phone resources like contacts, files, '
            'media, call logs, etc. One-time access can be taken for camera, microphone, location or '
            'similar for specific purposes with the consent of the borrower.'
        ),
        'expected_paragraph_ids': [],
        'category': 'direct',
    },
    {
        'question': 'What is the cooling-off or look-up period for digital loans?',
        'expected_answer': (
            'The borrower should be given an explicit cooling-off/look-up period to exit the digital loan '
            'without penalty. The Board of the Regulated Entity shall determine the period, and the borrower '
            'should be able to return the principal and the proportionate APR without any penalty during this period.'
        ),
        'expected_paragraph_ids': [],
        'category': 'direct',
    },
    {
        'question': 'Can loan disbursement for digital loans be made to a third party?',
        'expected_answer': (
            'Loan disbursement must be made directly into the bank account of the borrower. '
            'Disbursement should not be made through a third party, including Lending Service Providers (LSPs).'
        ),
        'expected_paragraph_ids': [],
        'category': 'direct',
    },
    {
        'question': 'What are the reporting requirements for digital lending to credit bureaus?',
        'expected_answer': (
            'All new digital loans including short-term loans must be reported to Credit Information Companies (CICs). '
            'The regulated entities should ensure reporting of all types of digital loans to credit bureaus.'
        ),
        'expected_paragraph_ids': [],
        'category': 'direct',
    },
    {
        'question': (
            'What are the roles and responsibilities of a Lending Service Provider (LSP) '
            'versus a Digital Lending App (DLA) in the digital lending ecosystem?'
        ),
        'expected_answer': (
            'An LSP is an agent of the Regulated Entity (RE) who carries out lending functions such as customer '
            'acquisition, underwriting, pricing, servicing, monitoring, recovery. A DLA is a mobile or web-based '
            'application used by borrowers to access digital lending services. Both must comply with RBI guidelines '
            'and the RE remains responsible for compliance.'
        ),
        'expected_paragraph_ids': [],
        'category': 'multi_para',
    },
    {
        'question': 'What is the maximum interest rate allowed by SEBI for mutual fund investments?',
        'expected_answer': 'Not applicable - this relates to SEBI, not covered in current documents.',
        'expected_paragraph_ids': [],
        'category': 'unanswerable',
    },
    {
        'question': 'What are the Basel III requirements for Indian banks in 2024?',
        'expected_answer': 'This information is not found in the loaded documents.',
        'expected_paragraph_ids': [],
        'category': 'unanswerable',
    },
    {
        'question': 'What happens if a digital lending app violates the RBI guidelines?',
        'expected_answer': 'This information is not found in the loaded documents.',
        'expected_paragraph_ids': [],
        'category': 'unanswerable',
    },
    {
        'question': 'What is the process for handling borrower grievances in digital lending?',
        'expected_answer': (
            'Regulated entities must ensure that they and their LSPs/DLAs have a suitable nodal grievance '
            'redressal officer to deal with complaints related to digital lending. Details of the grievance '
            'redressal officer must be disclosed to the borrower at the time of loan execution.'
        ),
        'expected_paragraph_ids': [],
        'category': 'direct',
    },
]


class Command(BaseCommand):
    help = 'Seed the database with gold-standard evaluation questions for the RAG system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing gold questions before seeding',
        )

    def handle(self, *args, **options):
        if options['clear']:
            count = GoldQuestion.objects.count()
            GoldQuestion.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Cleared {count} existing gold questions.'))

        created_count = 0
        skipped_count = 0

        for gq_data in GOLD_QUESTIONS:
            # Check if a similar question already exists
            if GoldQuestion.objects.filter(question=gq_data['question']).exists():
                skipped_count += 1
                continue

            GoldQuestion.objects.create(**gq_data)
            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Seeded {created_count} gold questions '
                f'({skipped_count} skipped as duplicates).'
            )
        )
