from django.contrib import admin
from .models import Document, Chunk, QueryLog, GoldQuestion, EvalRun, EvalResult

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'regulator', 'status', 'is_indexed', 'total_chunks', 'uploaded_at')
    list_filter = ('regulator', 'status', 'is_indexed')
    search_fields = ('title',)

@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ('document', 'paragraph_id', 'chunk_index', 'page_number')
    list_filter = ('document',)
    search_fields = ('text', 'paragraph_id')

@admin.register(QueryLog)
class QueryLogAdmin(admin.ModelAdmin):
    list_display = ('get_question_truncated', 'user', 'citation_verified', 'flagged', 'not_found', 'created_at')
    list_filter = ('flagged', 'not_found', 'citation_verified')
    search_fields = ('question', 'answer')
    readonly_fields = (
        'user', 'question', 'answer', 'retrieved_chunk_ids', 
        'confidence_scores', 'citation_verified', 'flagged', 
        'not_found', 'created_at', 'response_time_ms'
    )

    def get_question_truncated(self, obj):
        return obj.question[:80] + '...' if len(obj.question) > 80 else obj.question
    get_question_truncated.short_description = 'Question'

@admin.register(GoldQuestion)
class GoldQuestionAdmin(admin.ModelAdmin):
    list_display = ('get_question_truncated', 'category', 'document')
    list_filter = ('category',)

    def get_question_truncated(self, obj):
        return obj.question[:80] + '...' if len(obj.question) > 80 else obj.question
    get_question_truncated.short_description = 'Question'

class EvalResultInline(admin.TabularInline):
    model = EvalResult
    extra = 0
    readonly_fields = ('gold_question', 'system_answer', 'retrieved_chunk_ids', 'retrieval_correct', 'answer_quality', 'response_time_ms')
    can_delete = False

@admin.register(EvalRun)
class EvalRunAdmin(admin.ModelAdmin):
    list_display = ('run_at', 'total_questions', 'correct_retrievals', 'correct_refusals', 'get_accuracy')
    inlines = [EvalResultInline]
    
    def get_accuracy(self, obj):
        return f"{obj.accuracy():.1f}%"
    get_accuracy.short_description = 'Accuracy'

@admin.register(EvalResult)
class EvalResultAdmin(admin.ModelAdmin):
    list_display = ('get_gold_question_truncated', 'eval_run', 'answer_quality', 'retrieval_correct', 'response_time_ms')
    list_filter = ('answer_quality', 'retrieval_correct')
    search_fields = ('gold_question__question', 'system_answer')
    
    def get_gold_question_truncated(self, obj):
        return obj.gold_question.question[:50] + '...' if len(obj.gold_question.question) > 50 else obj.gold_question.question
    get_gold_question_truncated.short_description = 'Gold Question'
