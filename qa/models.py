from django.db import models
from django.contrib.auth.models import User

class Document(models.Model):
    """A regulatory document (PDF) uploaded to the system."""
    STATUS_CHOICES = [
        ('in_force', 'In Force'),
        ('amended', 'Amended'),
        ('repealed', 'Repealed'),
    ]
    title = models.CharField(max_length=500)
    file = models.FileField(upload_to='documents/')
    regulator = models.CharField(max_length=10, choices=[('RBI', 'RBI'), ('SEBI', 'SEBI')], default='RBI')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_force')
    effective_date = models.DateField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_indexed = models.BooleanField(default=False, help_text='Whether chunks have been embedded and indexed')
    total_chunks = models.IntegerField(default=0)
    
    def __str__(self):
        return f'{self.title} ({self.get_status_display()})'
    
    class Meta:
        ordering = ['-uploaded_at']


class Chunk(models.Model):
    """A clause/paragraph extracted from a Document."""
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='chunks')
    chunk_index = models.IntegerField(help_text='Sequential index of this chunk in the document')
    paragraph_id = models.CharField(max_length=100, blank=True, help_text='e.g. "3.1", "4(a)(ii)"')
    text = models.TextField()
    page_number = models.IntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True, help_text='Extra metadata (heading hierarchy, etc.)')
    
    def __str__(self):
        return f'{self.document.title} — §{self.paragraph_id or self.chunk_index}'
    
    class Meta:
        ordering = ['document', 'chunk_index']
        unique_together = ['document', 'chunk_index']


class QueryLog(models.Model):
    """Log of every query made to the system, for audit trail."""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    question = models.TextField()
    answer = models.TextField(blank=True)
    retrieved_chunk_ids = models.JSONField(default=list, blank=True)
    confidence_scores = models.JSONField(default=list, blank=True)
    citation_verified = models.BooleanField(default=False)
    flagged = models.BooleanField(default=False, help_text='True if citation check found issues')
    not_found = models.BooleanField(default=False, help_text='True if system said "not found"')
    created_at = models.DateTimeField(auto_now_add=True)
    response_time_ms = models.IntegerField(null=True, blank=True)
    
    def __str__(self):
        return f'Q: {self.question[:80]}...'
    
    class Meta:
        ordering = ['-created_at']


class GoldQuestion(models.Model):
    """Hand-written gold-standard Q&A for evaluation."""
    CATEGORY_CHOICES = [
        ('direct', 'Direct Lookup'),
        ('multi_para', 'Multi-Paragraph'),
        ('unanswerable', 'Unanswerable'),
    ]
    question = models.TextField()
    expected_answer = models.TextField(help_text='Expected answer text (for manual comparison)')
    expected_paragraph_ids = models.JSONField(default=list, blank=True, help_text='List of paragraph IDs that should be retrieved')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='direct')
    document = models.ForeignKey(Document, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        return f'[{self.get_category_display()}] {self.question[:80]}'


class EvalRun(models.Model):
    """A batch evaluation run."""
    run_at = models.DateTimeField(auto_now_add=True)
    total_questions = models.IntegerField(default=0)
    correct_retrievals = models.IntegerField(default=0)
    correct_refusals = models.IntegerField(default=0)
    false_answers = models.IntegerField(default=0)
    avg_response_time_ms = models.FloatField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    def accuracy(self):
        if self.total_questions == 0:
            return 0
        return (self.correct_retrievals + self.correct_refusals) / self.total_questions * 100
    
    def __str__(self):
        return f'EvalRun {self.run_at:%Y-%m-%d %H:%M} — {self.accuracy():.1f}% accuracy'


class EvalResult(models.Model):
    """Result for a single question in an eval run."""
    eval_run = models.ForeignKey(EvalRun, on_delete=models.CASCADE, related_name='results')
    gold_question = models.ForeignKey(GoldQuestion, on_delete=models.CASCADE)
    system_answer = models.TextField(blank=True)
    retrieved_chunk_ids = models.JSONField(default=list, blank=True)
    retrieval_correct = models.BooleanField(default=False)
    answer_quality = models.CharField(max_length=20, choices=[
        ('correct', 'Correct'),
        ('partial', 'Partially Correct'),
        ('wrong', 'Wrong'),
        ('refused', 'Correctly Refused'),
        ('false_refuse', 'Incorrectly Refused'),
    ], default='wrong')
    response_time_ms = models.IntegerField(null=True, blank=True)
    
    def __str__(self):
        return f'{self.gold_question.question[:50]} → {self.answer_quality}'
