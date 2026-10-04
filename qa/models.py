from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


CONFIDENCE_BANDS = [
    ('high', 'High'),
    ('medium', 'Medium'),
    ('low', 'Low'),
    ('insufficient', 'Insufficient'),
]

REVIEW_RESOLUTION_CHOICES = [
    ('open', 'Open'),
    ('resolved', 'Resolved'),
    ('dismissed', 'Dismissed'),
]


class Document(models.Model):
    """A regulatory source or company-policy document (PDF) uploaded to the system."""
    STATUS_CHOICES = [
        ('in_force', 'In Force'),
        ('amended', 'Amended'),
        ('repealed', 'Repealed'),
        ('draft', 'Draft / Consultation'),
        ('not_applicable', 'Not applicable'),
    ]
    DOCUMENT_TYPE_CHOICES = [
        ('regulation', 'Regulatory source'),
        ('company_policy', 'Company policy'),
    ]
    REGULATOR_CHOICES = [('RBI', 'RBI'), ('SEBI', 'SEBI')]
    SOURCE_CATEGORY_CHOICES = [
        ('unclassified', 'Unclassified'),
        ('binding_regulation', 'Binding regulation'),
        ('master_direction', 'Master direction'),
        ('circular', 'Circular'),
        ('consultation_paper', 'Consultation paper / draft circular'),
        ('guidance', 'Guidance'),
        ('report', 'Research or financial-stability report'),
        ('internal_policy', 'Internal company policy'),
    ]
    INDEX_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('ready', 'Ready'),
        ('error', 'Error'),
    ]

    title = models.CharField(max_length=500)
    file = models.FileField(upload_to='documents/')
    original_filename = models.CharField(max_length=255, blank=True)
    document_type = models.CharField(
        max_length=20, choices=DOCUMENT_TYPE_CHOICES, default='regulation', db_index=True,
    )
    regulator = models.CharField(max_length=10, choices=REGULATOR_CHOICES, default='RBI', blank=True)
    source_category = models.CharField(
        max_length=30, choices=SOURCE_CATEGORY_CHOICES, default='unclassified',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_force')
    effective_date = models.DateField(null=True, blank=True)
    source_url = models.URLField(blank=True)
    publication_date = models.DateField(null=True, blank=True)
    version_label = models.CharField(max_length=100, blank=True)
    version_family = models.CharField(max_length=100, blank=True, help_text='Shared rule identifier across dated versions.')
    printed_page_offset = models.IntegerField(
        default=0, help_text='Printed page = PDF page + offset (when a fixed offset applies).',
    )
    sha256 = models.CharField(max_length=64, blank=True, db_index=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='uploaded_documents',
    )
    is_indexed = models.BooleanField(default=False, help_text='Whether chunks have been embedded and indexed')
    index_status = models.CharField(max_length=10, choices=INDEX_STATUS_CHOICES, default='pending', db_index=True)
    index_error = models.TextField(blank=True)
    total_chunks = models.IntegerField(default=0)
    page_count = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f'{self.title} ({self.get_status_display()})'

    def clean(self):
        if self.document_type == 'regulation' and not self.regulator:
            raise ValidationError({'regulator': 'Regulatory documents require a regulator.'})
        if self.document_type == 'company_policy':
            if self.regulator:
                raise ValidationError({
                    'regulator': 'Company-policy documents must not be presented as RBI/SEBI publications.'
                })
            if self.source_category not in ('internal_policy', 'unclassified'):
                raise ValidationError({'source_category': 'Company policies must use the internal-policy category.'})

    @property
    def is_regulation(self) -> bool:
        return self.document_type == 'regulation'

    @property
    def source_label(self) -> str:
        if self.document_type == 'company_policy':
            return 'Company policy'
        return self.regulator or 'Regulatory source'

    class Meta:
        ordering = ['-uploaded_at']
        permissions = [
            ('upload_document', 'Can upload documents'),
            ('index_document', 'Can index/re-index documents'),
            ('manage_corpus', 'Can manage the corpus and vector index'),
        ]


class Chunk(models.Model):
    """A clause/paragraph extracted from a Document."""
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='chunks')
    chunk_index = models.IntegerField(help_text='Sequential index of this chunk in the document')
    paragraph_id = models.CharField(max_length=100, blank=True, help_text='e.g. "3.1", "4(a)(ii)"')
    text = models.TextField()
    # Deprecated: retained for compatibility; use start_page/end_page.
    page_number = models.IntegerField(null=True, blank=True)
    start_page = models.PositiveIntegerField(null=True, blank=True)
    end_page = models.PositiveIntegerField(null=True, blank=True)
    printed_start_page = models.CharField(max_length=20, blank=True)
    printed_end_page = models.CharField(max_length=20, blank=True)
    content_sha256 = models.CharField(max_length=64, blank=True, db_index=True)
    heading_path = models.JSONField(default=list, blank=True)
    chunker_version = models.CharField(max_length=20, blank=True)
    metadata = models.JSONField(default=dict, blank=True, help_text='Extra metadata (heading hierarchy, etc.)')

    def __str__(self):
        return f'{self.document.title} — §{self.paragraph_id or self.chunk_index}'

    @property
    def page_span(self) -> str:
        if not self.start_page:
            return ''
        if self.end_page and self.end_page != self.start_page:
            return f'{self.start_page}–{self.end_page}'
        return str(self.start_page)

    @property
    def printed_span(self) -> str:
        if not self.printed_start_page:
            return ''
        if self.printed_end_page and self.printed_end_page != self.printed_start_page:
            return f'{self.printed_start_page}–{self.printed_end_page}'
        return self.printed_start_page

    class Meta:
        ordering = ['document', 'chunk_index']
        unique_together = ['document', 'chunk_index']


class VectorIndexBuild(models.Model):
    """Audit record for every vector index generation build."""
    STATUS_CHOICES = [
        ('building', 'Building'),
        ('ready', 'Ready'),
        ('failed', 'Failed'),
        ('superseded', 'Superseded'),
    ]
    generation_id = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='building', db_index=True)
    embedding_model = models.CharField(max_length=200)
    vector_dimension = models.IntegerField()
    distance_metric = models.CharField(max_length=30, default='inner_product')
    normalized_embeddings = models.BooleanField(default=True)
    chunker_version = models.CharField(max_length=50, blank=True)
    corpus_fingerprint = models.CharField(max_length=64, blank=True)
    vector_count = models.IntegerField(default=0)
    build_started_at = models.DateTimeField(default=timezone.now)
    build_finished_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    is_active = models.BooleanField(default=False, db_index=True)
    triggered_by = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-build_started_at']

    def __str__(self):
        return f'{self.generation_id} ({self.status})'


class QueryLog(models.Model):
    """Log of every query made to the system, for audit trail."""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    question = models.TextField()
    answer = models.TextField(blank=True)
    answer_payload = models.JSONField(default=dict, blank=True)
    retrieved_chunk_ids = models.JSONField(default=list, blank=True)
    confidence_scores = models.JSONField(default=list, blank=True)
    citation_verified = models.BooleanField(default=False)
    flagged = models.BooleanField(default=False, help_text='True if citation check found issues')
    not_found = models.BooleanField(default=False, help_text='True if the system abstained')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    response_time_ms = models.IntegerField(null=True, blank=True)
    model_name = models.CharField(max_length=200, blank=True)
    prompt_version = models.CharField(max_length=50, blank=True)
    retrieval_config = models.JSONField(default=dict, blank=True)
    faithfulness_score = models.FloatField(null=True, blank=True)
    citation_precision = models.FloatField(null=True, blank=True)
    confidence_band = models.CharField(max_length=15, choices=CONFIDENCE_BANDS, blank=True, db_index=True)
    review_required = models.BooleanField(default=False, db_index=True)
    review_reason = models.TextField(blank=True)
    review_status = models.CharField(max_length=10, choices=REVIEW_RESOLUTION_CHOICES, default='open')
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_queries',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    agent_used = models.BooleanField(default=False)
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    error = models.TextField(blank=True)

    def __str__(self):
        return f'Q: {self.question[:80]}...'

    class Meta:
        ordering = ['-created_at']
        permissions = [
            ('view_global_logs', 'Can view all users\' query logs'),
        ]


class GoldQuestion(models.Model):
    """Hand-written gold-standard Q&A for evaluation."""
    CATEGORY_CHOICES = [
        ('direct', 'Direct Lookup'),
        ('multi_para', 'Multi-Paragraph'),
        ('unanswerable', 'Unanswerable'),
    ]
    SPLIT_CHOICES = [
        ('dev', 'Development'),
        ('test', 'Held-out test'),
    ]
    question = models.TextField()
    expected_answer = models.TextField(help_text='Reference answer text')
    expected_answer_notes = models.TextField(blank=True)
    # Deprecated: superseded by GoldEvidence. Kept for migration compatibility.
    expected_paragraph_ids = models.JSONField(
        default=list, blank=True, help_text='DEPRECATED — use Gold evidence rows instead.',
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='direct')
    split = models.CharField(max_length=10, choices=SPLIT_CHOICES, default='dev', db_index=True)
    gold_set_version = models.CharField(max_length=30, blank=True)
    document = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_gold_questions',
    )

    @property
    def is_answerable(self) -> bool:
        return self.category != 'unanswerable'

    @property
    def is_reviewed(self) -> bool:
        return self.reviewed_at is not None

    def __str__(self):
        return f'[{self.get_category_display()}] {self.question[:80]}'

    class Meta:
        permissions = [
            ('run_evaluation', 'Can run evaluations'),
        ]


class GoldEvidence(models.Model):
    """Stable evidence identity for a gold question: document + paragraph (+ optional text anchor)."""
    gold_question = models.ForeignKey(GoldQuestion, on_delete=models.CASCADE, related_name='evidence')
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='gold_evidence')
    paragraph_id = models.CharField(max_length=100)
    text_anchor = models.CharField(
        max_length=300, blank=True,
        help_text='Short verbatim phrase from the evidence passage; disambiguates repeated paragraph IDs.',
    )
    chunk = models.ForeignKey(
        Chunk, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
        help_text='Convenience pointer only; chunk IDs change on re-index.',
    )
    required = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['gold_question', 'document', 'paragraph_id'], name='unique_gold_evidence',
            ),
        ]

    def __str__(self):
        return f'{self.document_id}:§{self.paragraph_id}'


class EvalRun(models.Model):
    """A batch evaluation run."""
    run_at = models.DateTimeField(auto_now_add=True)
    label = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)
    total_questions = models.IntegerField(default=0)
    # Legacy summary counters (kept for historical runs).
    correct_retrievals = models.IntegerField(default=0)
    correct_refusals = models.IntegerField(default=0)
    false_answers = models.IntegerField(default=0)
    avg_response_time_ms = models.FloatField(null=True, blank=True)
    median_latency_ms = models.FloatField(null=True, blank=True)
    p95_latency_ms = models.FloatField(null=True, blank=True)
    retrieval_hit_at_1 = models.FloatField(null=True, blank=True)
    retrieval_hit_at_3 = models.FloatField(null=True, blank=True)
    retrieval_hit_at_k = models.FloatField(null=True, blank=True)
    retrieval_recall_at_k = models.FloatField(null=True, blank=True)
    retrieval_mrr = models.FloatField(null=True, blank=True)
    answer_correctness = models.FloatField(null=True, blank=True)
    faithfulness = models.FloatField(null=True, blank=True)
    citation_precision = models.FloatField(null=True, blank=True)
    correct_refusal_rate = models.FloatField(null=True, blank=True)
    false_refusal_rate = models.FloatField(null=True, blank=True)
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    status = models.CharField(max_length=12, default='complete')
    notes = models.TextField(blank=True)

    def accuracy(self):
        """Legacy combined figure. Not displayed for new runs (see separate metrics)."""
        if self.total_questions == 0:
            return 0
        return (self.correct_retrievals + self.correct_refusals) / self.total_questions * 100

    @property
    def is_legacy(self) -> bool:
        return not self.configuration

    def __str__(self):
        return f'EvalRun {self.label or self.pk} {self.run_at:%Y-%m-%d %H:%M}'


class EvalResult(models.Model):
    """Result for a single question in an eval run."""
    CORRECTNESS_CHOICES = [
        ('correct', 'Correct'),
        ('partial', 'Partial'),
        ('wrong', 'Wrong'),
        ('not_judged', 'Not judged'),
    ]
    eval_run = models.ForeignKey(EvalRun, on_delete=models.CASCADE, related_name='results')
    gold_question = models.ForeignKey(GoldQuestion, on_delete=models.CASCADE)
    system_answer = models.TextField(blank=True)
    answer_payload = models.JSONField(default=dict, blank=True)
    retrieved_chunk_ids = models.JSONField(default=list, blank=True)
    retrieved_evidence = models.JSONField(
        default=list, blank=True, help_text='Ranked [{document_id, paragraph_id, chunk_id, scores}]',
    )
    retrieval_correct = models.BooleanField(default=False)
    hit_rank = models.IntegerField(null=True, blank=True)
    recall_at_k = models.FloatField(null=True, blank=True)
    answer_quality = models.CharField(max_length=20, choices=[
        ('correct', 'Correct'),
        ('partial', 'Partially Correct'),
        ('wrong', 'Wrong'),
        ('refused', 'Correctly Refused'),
        ('false_refuse', 'Incorrectly Refused'),
        ('not_judged', 'Not judged'),
    ], default='wrong')
    correctness_label = models.CharField(max_length=12, choices=CORRECTNESS_CHOICES, default='not_judged')
    correctness_score = models.FloatField(null=True, blank=True)
    judge_model = models.CharField(max_length=200, blank=True)
    judge_prompt_version = models.CharField(max_length=50, blank=True)
    judge_explanation = models.TextField(blank=True)
    human_correctness_label = models.CharField(max_length=12, choices=CORRECTNESS_CHOICES, blank=True)
    faithfulness_score = models.FloatField(null=True, blank=True)
    unsupported_claim_ids = models.JSONField(default=list, blank=True)
    citation_precision = models.FloatField(null=True, blank=True)
    refused = models.BooleanField(default=False)
    refusal_correct = models.BooleanField(null=True, blank=True)
    response_time_ms = models.IntegerField(null=True, blank=True)
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    error = models.TextField(blank=True)

    def __str__(self):
        return f'{self.gold_question.question[:50]} → {self.correctness_label}'


class AgentRun(models.Model):
    STATUS_CHOICES = [
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('abstained', 'Abstained'),
        ('failed', 'Failed'),
    ]
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    query_log = models.OneToOneField(
        QueryLog, on_delete=models.SET_NULL, null=True, blank=True, related_name='agent_run',
    )
    question = models.TextField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='running')
    plan_summary = models.TextField(blank=True)
    sub_questions = models.JSONField(default=list, blank=True)
    final_answer_payload = models.JSONField(default=dict, blank=True)
    step_count = models.IntegerField(default=0)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ['-started_at']


class AgentStep(models.Model):
    STEP_TYPES = [
        ('plan', 'Plan'),
        ('tool', 'Tool call'),
        ('synthesis', 'Synthesis'),
        ('decision', 'Decision'),
    ]
    run = models.ForeignKey(AgentRun, on_delete=models.CASCADE, related_name='steps')
    position = models.IntegerField()
    step_type = models.CharField(max_length=12, choices=STEP_TYPES)
    tool_name = models.CharField(max_length=50, blank=True)
    tool_input = models.JSONField(default=dict, blank=True)
    output_summary = models.TextField(blank=True)
    evidence_chunk_ids = models.JSONField(default=list, blank=True)
    latency_ms = models.IntegerField(null=True, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ['run', 'position']
        unique_together = ['run', 'position']


class ObligationExtractionRecord(models.Model):
    """Tracks per-chunk extraction so batch extraction is idempotent and resumable."""
    STATUS_CHOICES = [('done', 'Done'), ('error', 'Error')]
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='extraction_records')
    chunk = models.ForeignKey(Chunk, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    content_sha256 = models.CharField(max_length=64)
    prompt_version = models.CharField(max_length=50)
    model_name = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    obligation_count = models.IntegerField(default=0)
    error = models.TextField(blank=True)
    review_status = models.CharField(max_length=10, choices=REVIEW_RESOLUTION_CHOICES, default='open')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['document', 'content_sha256', 'prompt_version'], name='unique_extraction_record',
            ),
        ]


class Obligation(models.Model):
    REVIEW_STATUS_CHOICES = [
        ('pending', 'Pending review'),
        ('confirmed', 'Confirmed'),
        ('edited', 'Edited & confirmed'),
        ('rejected', 'Rejected'),
    ]
    ENTAILMENT_CHOICES = [
        ('entailed', 'Entailed by source'),
        ('partial', 'Partially entailed'),
        ('not_entailed', 'Not entailed'),
        ('unavailable', 'Check unavailable'),
    ]
    source_document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='obligations')
    source_chunk = models.ForeignKey(
        Chunk, on_delete=models.SET_NULL, null=True, blank=True, related_name='obligations',
    )
    # Stable source identity (survives re-indexing).
    source_paragraph_id = models.CharField(max_length=100, blank=True)
    source_content_sha256 = models.CharField(max_length=64, blank=True, db_index=True)
    source_start_page = models.PositiveIntegerField(null=True, blank=True)
    source_end_page = models.PositiveIntegerField(null=True, blank=True)
    source_printed_pages = models.CharField(max_length=50, blank=True)
    source_quote = models.TextField(blank=True)
    quote_verified = models.BooleanField(default=False)
    obligation_text = models.TextField()
    obligated_party = models.CharField(max_length=300, blank=True, db_index=True)
    condition = models.TextField(blank=True)
    deadline_or_trigger = models.TextField(blank=True)
    extraction_confidence = models.CharField(max_length=15, choices=CONFIDENCE_BANDS, default='low', db_index=True)
    extraction_model = models.CharField(max_length=200, blank=True)
    prompt_version = models.CharField(max_length=50, blank=True)
    entailment_status = models.CharField(
        max_length=15, choices=ENTAILMENT_CHOICES, default='unavailable', db_index=True,
    )
    entailment_explanation = models.TextField(blank=True)
    review_status = models.CharField(
        max_length=10, choices=REVIEW_STATUS_CHOICES, default='pending', db_index=True,
    )
    reviewer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_obligations',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewer_notes = models.TextField(blank=True)
    original_values = models.JSONField(default=dict, blank=True, help_text='Extractor output before edits')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_confirmed(self) -> bool:
        return self.review_status in ('confirmed', 'edited')

    class Meta:
        ordering = ['source_document', 'source_start_page', 'id']
        permissions = [
            ('review_obligation', 'Can review extracted obligations'),
            ('extract_obligations', 'Can run obligation extraction'),
        ]

    def __str__(self):
        return self.obligation_text[:80]


class GapAnalysisRun(models.Model):
    STATUS_CHOICES = [
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    policy_document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='gap_runs_as_policy')
    regulatory_documents = models.ManyToManyField(Document, related_name='gap_runs_as_regulation', blank=True)
    scope = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='running')
    configuration = models.JSONField(default=dict, blank=True)
    corpus_fingerprint = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    counts = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        permissions = [
            ('run_gap_analysis', 'Can run gap analyses'),
        ]


class GapFinding(models.Model):
    STATUS_CHOICES = [
        ('addressed', 'Addressed'),
        ('partially_addressed', 'Partially addressed'),
        ('not_addressed', 'Potential gap — not addressed'),
        ('conflicting', 'Potential conflict'),
        ('needs_review', 'Needs review'),
    ]
    REVIEW_STATUS_CHOICES = [
        ('pending', 'Pending review'),
        ('accepted', 'Accepted'),
        ('overridden', 'Overridden'),
    ]
    run = models.ForeignKey(GapAnalysisRun, on_delete=models.CASCADE, related_name='findings')
    obligation = models.ForeignKey(Obligation, on_delete=models.CASCADE, related_name='gap_findings')
    matched_policy_chunk = models.ForeignKey(
        Chunk, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, db_index=True)
    explanation = models.TextField(blank=True)
    regulatory_evidence = models.JSONField(default=dict, blank=True)
    policy_evidence = models.JSONField(default=dict, blank=True)
    candidate_policy_chunk_ids = models.JSONField(default=list, blank=True)
    model_name = models.CharField(max_length=200, blank=True)
    prompt_version = models.CharField(max_length=50, blank=True)
    confidence_band = models.CharField(max_length=15, choices=CONFIDENCE_BANDS, default='low')
    review_status = models.CharField(max_length=12, choices=REVIEW_STATUS_CHOICES, default='pending', db_index=True)
    reviewer_status_override = models.CharField(max_length=20, choices=STATUS_CHOICES, blank=True)
    reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewer_notes = models.TextField(blank=True)
    error = models.TextField(blank=True)

    @property
    def effective_status(self) -> str:
        return self.reviewer_status_override or self.status

    def get_effective_status_display(self) -> str:
        return dict(self.STATUS_CHOICES).get(self.effective_status, self.effective_status)

    class Meta:
        ordering = ['run', 'id']
