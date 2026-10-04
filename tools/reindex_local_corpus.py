"""One-time repair of metadata evidenced by the already-loaded PDFs.

Invoked through manage.py shell; no assumptions about document primary keys.
"""
from qa.models import Document
from qa.services.documents import index_document

for doc in Document.objects.filter(document_type='regulation'):
    text = ' '.join(doc.chunks.order_by('chunk_index').values_list('text', flat=True)[:4])
    if 'Consultation Paper on Measures to strengthen index derivatives' in text:
        doc.source_category, doc.status = 'consultation_paper', 'draft'
    elif 'Financial Institutions: Soundness and Resilience' in text:
        doc.source_category, doc.status = 'report', 'not_applicable'
        doc.printed_page_offset = 59
    else:
        continue
    doc.save()
    print(f'Indexing document {doc.pk} ({doc.source_category})', flush=True)
    count = index_document(doc.pk)
    print(f'Document {doc.pk}: {count} chunks', flush=True)
