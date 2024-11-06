from sentence_transformers import SentenceTransformer
from langchain.embeddings.base import Embeddings
from typing import List

class MyEmbeddings(Embeddings):
        def __init__(self):
            self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    
        def embed_documents(self, texts: List[str]) -> List[List[float]]:
            return [self.model.encode(t).tolist() for t in texts]
        
        def embed_query(self, text: str) -> List[float]:
            return self.model.encode(text).tolist()

embedding_func = MyEmbeddings()