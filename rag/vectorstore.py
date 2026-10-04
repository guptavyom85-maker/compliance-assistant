"""Immutable generations activated through one atomic pointer; no pickle loading."""
import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path
import faiss
import numpy as np
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from filelock import FileLock
from .embedder import embed_texts, embed_query

class IndexIntegrityError(RuntimeError):
    pass

def replace_pointer(source, destination):
    """Retry transient Windows sharing violations without removing the old pointer."""
    for attempt in range(5):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.05 * (2 ** attempt))

def digest_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def corpus_lock(store_dir=None):
    root = Path(store_dir or settings.VECTORSTORE_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return FileLock(str(root / '.corpus.lock'), timeout=30)

def corpus_rows():
    from qa.models import Chunk
    return list(Chunk.objects.select_related('document').order_by('id'))

def fingerprint(rows):
    # Actual text is included so outdated cached hashes cannot mask edits.
    payload = [(c.id, c.document_id, c.text, c.paragraph_id, c.start_page, c.end_page,
                c.printed_start_page, c.printed_end_page, c.chunker_version,
                c.document.title, c.document.document_type, c.document.source_category,
                c.document.status, str(c.document.effective_date), c.document.version_label,
                c.document.version_family, str(c.document.publication_date), c.document.source_url)
               for c in rows]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()

class VectorStore:
    def __init__(self, store_dir=None, rows=None):
        self.root = Path(store_dir or settings.VECTORSTORE_DIR)
        try:
            generation = (self.root / 'CURRENT').read_text(encoding='utf-8').strip()
            if not re.fullmatch(r'[0-9a-f]{32}', generation):
                raise ValueError('Invalid generation identifier')
            folder = self.root / 'generations' / generation
            self.manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
            if set(self.manifest['files']) != {'faiss_index.bin', 'id_mapping.json'}:
                raise ValueError('Incomplete checksums')
            for name, expected in self.manifest['files'].items():
                if digest_file(folder / name) != expected:
                    raise ValueError('Index file checksum mismatch')
            self.id_mapping = json.loads((folder / 'id_mapping.json').read_text())
            self.index = faiss.read_index(str(folder / 'faiss_index.bin'))
            self.rows = rows if rows is not None else corpus_rows()
            m = self.manifest
            valid = (m['schema_version'] == 1 and m['generation_id'] == generation
                     and m['embedding_model'] == settings.EMBEDDING_MODEL
                     and m['vector_dimension'] == settings.EMBEDDING_DIMENSION == self.index.d
                     and m['distance_metric'] == 'inner_product'
                     and self.index.metric_type == faiss.METRIC_INNER_PRODUCT
                     and m['normalized_embeddings'] is True
                     and m['vector_count'] == self.index.ntotal == len(self.id_mapping)
                     and self.id_mapping == [c.id for c in self.rows]
                     and len(set(self.id_mapping)) == len(self.id_mapping)
                     and m['corpus_fingerprint'] == fingerprint(self.rows))
            if not valid:
                raise ValueError('Index configuration or corpus changed')
        except Exception as exc:
            raise IndexIntegrityError('Index rebuild required: active index is missing, incompatible, or stale.') from exc

    @property
    def is_empty(self):
        return self.index.ntotal == 0

    def search(self, query, top_k=5):
        if self.is_empty:
            return []
        embedding = np.asarray(embed_query(query), dtype='float32').reshape(1, -1)
        scores, positions = self.index.search(embedding, min(top_k, self.index.ntotal))
        return [(self.id_mapping[int(pos)], float(score)) for pos, score in zip(positions[0], scores[0]) if pos >= 0]

def rebuild(store_dir=None, triggered_by='', already_locked=False):
    if not already_locked:
        with corpus_lock(store_dir):
            return rebuild(store_dir, triggered_by, already_locked=True)
    from qa.models import VectorIndexBuild, Document
    root = Path(store_dir or settings.VECTORSTORE_DIR)
    generation = uuid.uuid4().hex
    rows = corpus_rows()
    corpus_hash = fingerprint(rows)
    build = VectorIndexBuild.objects.create(
        generation_id=generation, embedding_model=settings.EMBEDDING_MODEL,
        vector_dimension=settings.EMBEDDING_DIMENSION, corpus_fingerprint=corpus_hash,
        chunker_version=','.join(sorted({c.chunker_version for c in rows})), triggered_by=triggered_by)
    folder = root / 'generations' / (generation + '.building')
    activated = False
    try:
        folder.mkdir(parents=True)
        index = faiss.IndexFlatIP(settings.EMBEDDING_DIMENSION)
        for start in range(0, len(rows), 32):
            batch = rows[start:start + 32]
            vectors = embed_texts([c.text for c in batch])
            if vectors.shape != (len(batch), index.d) or not np.isfinite(vectors).all():
                raise ValueError('Embedding dimensions or values are invalid')
            if not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-3):
                raise ValueError('Embeddings must be normalized')
            index.add(vectors)
        ids = [c.id for c in rows]
        faiss.write_index(index, str(folder / 'faiss_index.bin'))
        (folder / 'id_mapping.json').write_text(json.dumps(ids), encoding='utf-8')
        manifest = dict(schema_version=1, generation_id=generation,
                        embedding_model=settings.EMBEDDING_MODEL, vector_dimension=index.d,
                        distance_metric='inner_product', normalized_embeddings=True,
                        chunker_version=build.chunker_version, corpus_fingerprint=corpus_hash,
                        vector_count=index.ntotal, build_time=timezone.now().isoformat(),
                        files={n: digest_file(folder / n) for n in ('faiss_index.bin', 'id_mapping.json')})
        (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        reloaded = faiss.read_index(str(folder / 'faiss_index.bin'))
        if reloaded.ntotal != len(ids) or reloaded.d != index.d or json.loads((folder / 'id_mapping.json').read_text()) != ids:
            raise ValueError('Generation verification failed')
        if fingerprint(corpus_rows()) != corpus_hash:
            raise ValueError('Corpus changed while building; retry')
        folder.rename(root / 'generations' / generation)
        pointer = root / (generation + '.pointer')
        with pointer.open('w', encoding='utf-8') as stream:
            stream.write(generation)
            stream.flush()
            os.fsync(stream.fileno())
        replace_pointer(pointer, root / 'CURRENT')
        activated = True
        with transaction.atomic():
            VectorIndexBuild.objects.exclude(pk=build.pk).filter(is_active=True).update(is_active=False, status='superseded')
            build.status, build.is_active = 'ready', True
            build.vector_count, build.build_finished_at = len(ids), timezone.now()
            build.save()
            for doc in Document.objects.all():
                count = sum(c.document_id == doc.id for c in rows)
                Document.objects.filter(pk=doc.pk).update(total_chunks=count, is_indexed=bool(count),
                    index_status='ready' if count else 'pending', index_error='')
        return manifest
    except Exception as exc:
        build.status = 'failed'
        build.error = ('Activated generation; audit update failed. ' if activated else '') + type(exc).__name__
        build.build_finished_at = timezone.now()
        build.save(update_fields=['status', 'error', 'build_finished_at'])
        raise
