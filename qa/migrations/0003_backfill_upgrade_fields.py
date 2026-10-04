"""
Data backfill for the compliance upgrade.

* Chunk.start_page/end_page from the legacy page_number (a chunk was previously
  recorded only at its starting page, so end_page = start_page is the honest
  backfill until the document is re-chunked).
* Chunk.content_sha256 from text; chunker_version marked as legacy.
* Document.index_status from is_indexed; Document.sha256 from the stored file.
* GoldEvidence rows from any populated expected_paragraph_ids (only when the
  gold question names a document — evidence is never invented).
"""
import hashlib
import os

from django.db import migrations


def forwards(apps, schema_editor):
    Document = apps.get_model('qa', 'Document')
    Chunk = apps.get_model('qa', 'Chunk')
    GoldQuestion = apps.get_model('qa', 'GoldQuestion')
    GoldEvidence = apps.get_model('qa', 'GoldEvidence')

    for doc in Document.objects.all():
        doc.index_status = 'ready' if doc.is_indexed else 'pending'
        name = doc.file.name if doc.file else ''
        doc.original_filename = os.path.basename(name)[:255]
        try:
            path = doc.file.path
            if os.path.exists(path):
                digest = hashlib.sha256()
                with open(path, 'rb') as fh:
                    for block in iter(lambda: fh.read(1024 * 1024), b''):
                        digest.update(block)
                doc.sha256 = digest.hexdigest()
        except Exception:  # pragma: no cover - storage without paths
            pass
        doc.save(update_fields=['index_status', 'original_filename', 'sha256'])

    batch = []
    for chunk in Chunk.objects.all().iterator():
        chunk.start_page = chunk.page_number
        chunk.end_page = chunk.page_number
        chunk.printed_start_page = str(chunk.page_number) if chunk.page_number else ''
        chunk.printed_end_page = chunk.printed_start_page
        chunk.content_sha256 = hashlib.sha256(chunk.text.encode('utf-8')).hexdigest()
        chunk.chunker_version = 'legacy-1'
        batch.append(chunk)
        if len(batch) >= 500:
            Chunk.objects.bulk_update(batch, [
                'start_page', 'end_page', 'printed_start_page', 'printed_end_page',
                'content_sha256', 'chunker_version',
            ])
            batch = []
    if batch:
        Chunk.objects.bulk_update(batch, [
            'start_page', 'end_page', 'printed_start_page', 'printed_end_page',
            'content_sha256', 'chunker_version',
        ])

    for gq in GoldQuestion.objects.all():
        gq.gold_set_version = gq.gold_set_version or 'v0-legacy'
        gq.save(update_fields=['gold_set_version'])
        if not gq.expected_paragraph_ids or not gq.document_id:
            continue
        for pid in gq.expected_paragraph_ids:
            GoldEvidence.objects.get_or_create(
                gold_question=gq, document_id=gq.document_id, paragraph_id=str(pid),
                defaults={'notes': 'Migrated from expected_paragraph_ids; requires human review.'},
            )


def backwards(apps, schema_editor):
    # Schema rollback drops the new columns; nothing to undo for data.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('qa', '0002_compliance_upgrade_schema'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
