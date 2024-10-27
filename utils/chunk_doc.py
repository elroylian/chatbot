###
### Naive chunking of a document into smaller chunks
###
def get_cst_token_chunks(text, tokenizer, chunk_size=250, chunk_overlap=50):
  try:
    tokens = tokenizer.encode(text, add_special_tokens=False)
    chunks = []
    
    start = 0
    while start < len(tokens):
        end = start + chunk_size
        chunk = tokens[start:end]
        chunks.append(tokenizer.decode(chunk))
        
        start += (chunk_size - chunk_overlap)
        
        # Break if the end of the tokens is reached
        if end >= len(tokens):
            break
          
    return chunks
  except Exception as e:
    raise RuntimeError(f"Error chunking text: {e}")
  
###
### Sentence chunking of a document into smaller chunks
###

import os
import nltk
from transformers import AutoTokenizer

def ensure_nltk_data(package_name, nltk_data_path):
    if package_name == "punkt" or package_name == "punkt_tab":
        package_dir = os.path.join(nltk_data_path, "tokenizers", package_name)
        zip_file = os.path.join(package_dir, "tokenizers",f"{package_name}.zip")
    else:
        package_dir = os.path.join(nltk_data_path, package_name)
        zip_file = os.path.join(package_dir, f"{package_name}.zip")
        
    print(f"Checking for {package_name} data in {package_dir}")
    if os.path.exists(package_dir) or os.path.exists(zip_file):
        print(f"{package_name} data found in {package_dir}")
    else:
        print(f"{package_name} data not found in {package_dir}")
        print(f"Downloading {package_name} data")
        nltk.download(package_name, download_dir=nltk_data_path)
        if os.path.exists(package_dir) or os.path.exists(zip_file):
            print(f"{package_name} data downloaded successfully")
        else:
            print(f"Error downloading {package_name} data")
            
# Get the NLTK data path
nltk_data_path = nltk.data.path[0]

# Ensure the NLTK data is downloaded
ensure_nltk_data("punkt", nltk_data_path)
ensure_nltk_data("punkt_tab", nltk_data_path)

def get_sentence_chunks(text, tokenizer, min_chunk_size=150, max_chunk_size=250, overlap_size=50):
    try:
        # Tokenize the text into sentences
        sentences = nltk.sent_tokenize(text)

        # Initialize variables
        chunks = []  # List to hold all chunks
        current_chunk_tokens = []  # Current chunk tokens
        current_chunk_length = 0  # Current chunk length

        # Process each sentence
        for sentence in sentences:
            # Tokenize the sentence into subword tokens
            sentence_tokens = tokenizer.encode(sentence, add_special_tokens=False, truncation=False)
            sentence_length = len(sentence_tokens)

            # If the sentence is longer than max_chunk_size, split it
            if sentence_length > max_chunk_size:
                for i in range(0, sentence_length, max_chunk_size):
                    chunk_tokens = sentence_tokens[i:i + max_chunk_size]
                    chunks.append(tokenizer.decode(chunk_tokens))
                continue  # Move to next sentence after handling long sentence

            # Check if the current chunk will exceed max_chunk_size
            if current_chunk_length + sentence_length > max_chunk_size:
                # Add the current chunk to the list
                chunks.append(tokenizer.decode(current_chunk_tokens))

                # Start a new chunk with overlap if necessary
                current_chunk_tokens = current_chunk_tokens[-overlap_size:] if overlap_size > 0 else []
                current_chunk_length = len(current_chunk_tokens)

            # Add sentence tokens to the current chunk
            current_chunk_tokens.extend(sentence_tokens)
            current_chunk_length += sentence_length

        # Add any remaining tokens as the last chunk
        if current_chunk_tokens and current_chunk_length >= min_chunk_size:
            chunks.append(tokenizer.decode(current_chunk_tokens))

        return chunks

    except Exception as e:
        print(f"An error occurred: {e}")
        return []

###
### Append chunks to the vector store
###

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


from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

# Initialize ChromaDB client
vector_store = Chroma(
    # client = client,
    collection_name="markdown_chunks_collection",
    embedding_function=embedding_func,
    persist_directory = "db/pdfs",
    # other params...
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
        
def get_retriever():
    retriever = vector_store.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 10, "fetch_k": 20, "lambda_mult": 0.5},
    )
    
    return retriever