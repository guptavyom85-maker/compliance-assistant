import os
import faiss
import numpy as np
import pickle
from .embedder import embed_texts, embed_query

class VectorStore:
    def __init__(self, store_dir: str):
        self.store_dir = store_dir
        self.index_path = os.path.join(store_dir, 'faiss_index.bin')
        self.mapping_path = os.path.join(store_dir, 'id_mapping.pkl')
        self.dimension = 384
        
        os.makedirs(self.store_dir, exist_ok=True)
        self.load()
        
    def add_chunks(self, chunk_ids: list[int], texts: list[str]):
        if not chunk_ids or not texts:
            return
            
        if len(chunk_ids) != len(texts):
            raise ValueError("Mismatched chunk_ids and texts count")
            
        embeddings = embed_texts(texts)
        self.index.add(embeddings)
        self.id_mapping.extend(chunk_ids)
        
    def search(self, query: str, top_k: int = 5) -> list[tuple[int, float]]:
        if self.is_empty:
            return []
            
        query_embedding = embed_query(query)
            
        distances, indices = self.index.search(query_embedding.reshape(1, -1), top_k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx != -1 and idx < len(self.id_mapping):
                chunk_id = self.id_mapping[idx]
                score = float(distances[0][i])
                results.append((chunk_id, score))
                
        return results

    def remove_document_chunks(self, chunk_ids: list[int]):
        if not chunk_ids or self.is_empty:
            return
        
        ids_to_remove = set(chunk_ids)
        keep_indices = [i for i, cid in enumerate(self.id_mapping) if cid not in ids_to_remove]
        
        if len(keep_indices) == len(self.id_mapping):
            return
            
        new_index = faiss.IndexFlatIP(self.dimension)
        if keep_indices:
            vectors = np.vstack([self.index.reconstruct(i) for i in keep_indices])
            new_index.add(vectors)
            
        self.index = new_index
        self.id_mapping = [self.id_mapping[i] for i in keep_indices]
        
    def save(self):
        faiss.write_index(self.index, self.index_path)
        with open(self.mapping_path, 'wb') as f:
            pickle.dump(self.id_mapping, f)
            
    def load(self):
        if os.path.exists(self.index_path) and os.path.exists(self.mapping_path):
            self.index = faiss.read_index(self.index_path)
            with open(self.mapping_path, 'rb') as f:
                self.id_mapping = pickle.load(f)
        else:
            self.index = faiss.IndexFlatIP(self.dimension)
            self.id_mapping = []

    @property
    def is_empty(self) -> bool:
        return self.index.ntotal == 0
