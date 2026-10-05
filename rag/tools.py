"""Read-only, typed agent capabilities. No arbitrary filesystem/network/code access."""
from pydantic import Field
from .schemas import StrictModel


class SearchInput(StrictModel):
    query: str = Field(min_length=1, max_length=2000)
    document_ids: list[int] = Field(default_factory=list, max_length=10)
    top_k: int = Field(default=5, ge=1, le=10)


class MetadataInput(StrictModel):
    document_ids: list[int] = Field(min_length=1, max_length=10)


class ChunksInput(StrictModel):
    chunk_ids: list[int] = Field(min_length=1, max_length=20)


class CompareInput(StrictModel):
    document_a: int
    document_b: int
    topic: str = Field(min_length=1, max_length=2000)


def execute(name, arguments, search_fn, allowed_document_ids=None):
    from qa.models import Document, Chunk
    from .retriever import evidence_dict
    allowed = None if allowed_document_ids is None else set(allowed_document_ids)
    def require_scope(document_ids):
        if allowed is not None and not set(document_ids).issubset(allowed):
            raise ValueError('Tool requested a document outside the selected scope.')
    if name == 'search_documents':
        args = SearchInput.model_validate(arguments)
        require_scope(args.document_ids)
        return search_fn(args.query, document_ids=args.document_ids or None, top_k=args.top_k)
    if name == 'get_document_metadata':
        args = MetadataInput.model_validate(arguments)
        require_scope(args.document_ids)
        return list(Document.objects.filter(id__in=args.document_ids).values(
            'id', 'title', 'document_type', 'status', 'source_category', 'version_label',
            'effective_date', 'publication_date'))
    if name == 'get_chunks':
        args = ChunksInput.model_validate(arguments)
        chunks = list(Chunk.objects.filter(id__in=args.chunk_ids).select_related('document'))
        require_scope([chunk.document_id for chunk in chunks])
        return [evidence_dict(c) for c in chunks]
    if name == 'compare_documents':
        args = CompareInput.model_validate(arguments)
        require_scope([args.document_a, args.document_b])
        if args.document_a == args.document_b:
            raise ValueError('Comparison requires two distinct documents.')
        return search_fn(args.topic, document_ids=[args.document_a], top_k=3) + search_fn(
            args.topic, document_ids=[args.document_b], top_k=3)
    raise ValueError('Tool is not allowed.')
