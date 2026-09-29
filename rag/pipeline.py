from .vectorstore import VectorStore
from .retriever import retrieve
from .llm import NOT_FOUND_MSG, generate_answer
from .citation_checker import check_citations

def answer_question(question: str, vector_store_dir: str, api_key: str, top_k: int = 5, threshold: float = 0.3) -> dict:
    vector_store = VectorStore(vector_store_dir)
    
    retrieved = retrieve(question, vector_store, top_k, threshold)
    
    if not retrieved:
        return {
            'answer': "This information is not found in the loaded documents.",
            'chunks': [],
            'citation_check': {},
            'not_found': True,
            'retrieval_scores': []
        }
        
    from qa.models import Chunk
    
    chunk_ids = [r['chunk_id'] for r in retrieved]
    
    db_chunks = {
        chunk.id: chunk
        for chunk in Chunk.objects.filter(id__in=chunk_ids).select_related('document')
    }
    
    context_chunks = []
    for chunk_id in chunk_ids:
        c = db_chunks.get(chunk_id)
        if c is None:
            continue
        context_chunks.append({
            'chunk_id': c.id,
            'text': c.text,
            'paragraph_id': c.paragraph_id,
            'page_number': c.page_number,
            'document_title': c.document.title if c.document else '',
            'document_status': c.document.status if hasattr(c.document, 'status') else ''
        })
        
    answer = generate_answer(question, context_chunks, api_key)
    citation_check = check_citations(answer, context_chunks)
    not_found = answer.strip() == NOT_FOUND_MSG
    
    return {
        'answer': answer,
        'chunks': context_chunks,
        'citation_check': citation_check,
        'not_found': not_found,
        'retrieval_scores': retrieved
    }

def index_document(document_id: int, vector_store_dir: str) -> int:
    from qa.models import Document, Chunk
    
    doc = Document.objects.get(id=document_id)
    chunks = Chunk.objects.filter(document=doc).order_by('chunk_index')
    
    if not chunks.exists():
        return 0
        
    chunk_ids = []
    texts = []
    for chunk in chunks:
        chunk_ids.append(chunk.id)
        texts.append(chunk.text)
        
    vector_store = VectorStore(vector_store_dir)
    vector_store.add_chunks(chunk_ids, texts)
    vector_store.save()
    
    return len(chunk_ids)
