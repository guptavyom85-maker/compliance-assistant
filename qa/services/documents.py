from django.db import transaction
from qa.models import Chunk, Document, GoldQuestion
from rag.chunker import chunk_pdf
from rag.vectorstore import corpus_lock, rebuild


def index_document(document_id, store_dir=None):
    with corpus_lock(store_dir):
        doc = Document.objects.get(pk=document_id)
        from qa.forms import validate_pdf
        with doc.file.open('rb') as source:
            validate_pdf(source)
        raw = chunk_pdf(doc.file.path, doc.title, doc.printed_page_offset)
        if not raw:
            raise ValueError('No readable text; OCR is not enabled.')
        try:
            with transaction.atomic():
                existing = {c.chunk_index: c for c in doc.chunks.all()}
                changed, retained = False, []
                for data in raw:
                    old = existing.get(data['chunk_index'])
                    if old and old.content_sha256 == data['content_sha256'] and old.paragraph_id == data['paragraph_id']:
                        for key, value in data.items():
                            setattr(old, key, value)
                        old.save()
                        retained.append(old.pk)
                    else:
                        changed = True
                        if old:
                            old.delete()
                        retained.append(Chunk.objects.create(document=doc, **data).pk)
                removed = doc.chunks.exclude(pk__in=retained)
                changed = changed or removed.exists()
                removed.delete()
                if changed:
                    GoldQuestion.objects.filter(evidence__document=doc).update(reviewed_at=None, reviewed_by=None)
                doc.index_status, doc.is_indexed = 'pending', False
                doc.save(update_fields=['index_status', 'is_indexed'])
            rebuild(store_dir, f'document:{doc.pk}', already_locked=True)
            return len(raw)
        except Exception as exc:
            Document.objects.filter(pk=doc.pk).update(index_status='error', is_indexed=False, index_error=type(exc).__name__)
            raise


def delete_document(document_id, store_dir=None):
    with corpus_lock(store_dir):
        doc = Document.objects.get(pk=document_id)
        with transaction.atomic():
            GoldQuestion.objects.filter(evidence__document=doc).update(reviewed_at=None, reviewed_by=None)
            doc.delete()
        # Retain uploaded bytes for recovery. A failed rebuild makes queries fail closed.
        return rebuild(store_dir, f'delete:{document_id}', already_locked=True)
