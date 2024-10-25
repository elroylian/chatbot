import chromadb
from pathlib import Path
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter as Rec
from langchain.embeddings.base import Embeddings
from typing import List

class MyEmbeddings(Embeddings):
        def __init__(self):
            self.model = SentenceTransformer('sentence-transformers/multi-qa-MiniLM-L6-cos-v1')
    
        def embed_documents(self, texts: List[str]) -> List[List[float]]:
            return [self.model.encode(t).tolist() for t in texts]
        
        def embed_query(self, query: str) -> List[float]:
            return self.model.encode(query).tolist()

embedding_func = MyEmbeddings()

# Initialize ChromaDB client
client = chromadb.PersistentClient(path="db/pdfs")

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

vector_store = Chroma(
    client = client,
    collection_name="markdown_chunks_collection",
    embedding_function=embedding_func,
)

def split_chunks():
    try:
        # Path to markdown directory
        md_dir = Path("data/md/")
        chunk_id_counter = 1  # Initialize a counter for unique chunk IDs
        ids = []
        documents = []

        # Loop through all markdown files in the md directory
        for md_file in md_dir.glob("*.md"):
            with open(md_file, "r") as f:
                md_content = f.read()

            # Chunk the markdown content
            ## Chunk Method 1: Sentence Chunking
            # chunks = get_sentence_chunks(md_content, tokenizer)
            
            ## Chunk Method 2: CST Token Chunking
            # chunks = get_cst_token_chunks(md_content, tokenizer)
            
            ## Chunk Method 3: Recursive Character Chunking
            text_splitter = Rec(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
                add_start_index=True
            )
            chunks = text_splitter.split_text(md_content)
            
            for chunk in chunks:
                # Create a Document object for the chunk
                document_to_add = Document(
                    page_content = chunk,
                    metadata = {"source": str(md_file)}
                )
                
                documents.append(document_to_add)
                
                ids.append(str(chunk_id_counter)) # Add document ID to the list

                chunk_id_counter += 1  # Increment the ID counter
        
        vector_store.add_documents(documents = documents, ids = ids)
    except Exception as e:
        print(f"Error: {e}")

def run_init():
    split_chunks()

def get_retriever():
    retriever = vector_store.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 10, "fetch_k": 20, "lambda_mult": 0.5},
    )
    
    return retriever