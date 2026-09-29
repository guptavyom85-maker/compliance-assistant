from .vectorstore import VectorStore

def retrieve(query: str, vector_store: VectorStore, top_k: int = 5, threshold: float = 0.3) -> list[dict]:
    results = vector_store.search(query, top_k=top_k)
    filtered = [{'chunk_id': cid, 'score': score} for cid, score in results if score >= threshold]
    return filtered
