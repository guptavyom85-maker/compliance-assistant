from django.contrib import admin
from .models import Document, Chunk, QueryLog, GoldQuestion, GoldEvidence, EvalRun, EvalResult, VectorIndexBuild

class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Document)
class DocumentAdmin(ReadOnlyAdmin):
    list_display = ('title', 'document_type', 'source_category', 'status', 'index_status', 'total_chunks')
    list_filter = ('document_type', 'source_category', 'index_status')
    search_fields = ('title',)

@admin.register(Chunk)
class ChunkAdmin(ReadOnlyAdmin):
    list_display = ('document', 'paragraph_id', 'chunk_index', 'start_page', 'end_page')
    list_filter = ('document',)
    search_fields = ('text', 'paragraph_id')

@admin.register(QueryLog)
class QueryLogAdmin(ReadOnlyAdmin):
    list_display = ('question', 'user', 'confidence_band', 'review_required', 'created_at')

class GoldEvidenceInline(admin.TabularInline):
    model = GoldEvidence
    extra = 0

@admin.register(GoldQuestion)
class GoldQuestionAdmin(admin.ModelAdmin):
    list_display = ('question', 'category', 'split', 'is_active', 'reviewed_at')
    list_filter = ('split', 'category', 'is_active')
    readonly_fields = ('reviewed_at', 'reviewed_by')
    exclude = ('expected_paragraph_ids',)
    inlines = [GoldEvidenceInline]

    def save_model(self, request, obj, form, change):
        obj.reviewed_at = obj.reviewed_by = None
        super().save_model(request, obj, form, change)

@admin.register(EvalRun)
class EvalRunAdmin(ReadOnlyAdmin):
    list_display = ('label', 'run_at', 'status', 'total_questions', 'answer_correctness', 'faithfulness')

@admin.register(EvalResult)
class EvalResultAdmin(ReadOnlyAdmin):
    list_display = ('gold_question', 'eval_run', 'correctness_label', 'correctness_score', 'error')

@admin.register(VectorIndexBuild)
class IndexBuildAdmin(ReadOnlyAdmin):
    list_display = ('generation_id', 'status', 'is_active', 'vector_count', 'build_finished_at')
