import asyncio
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter as Rec
from langchain_huggingface import HuggingFaceEmbeddings
from utils.rank_bm25 import find_closest_chunks_bm25

async def load_pages():
    file_path = r"data/books/introduction-to-algorithms-trimmed.pdf"
    loader = PyPDFLoader(file_path)
    pages = []
    async for page in loader.alazy_load():
        pages.append(page.page_content)
    return pages  
    

text_splitter = Rec(
  chunk_size=250,
  chunk_overlap=50,
  length_function=len,
  add_start_index=True
)

# This is naive chunking
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

# pages = asyncio.run(load_pages())

# chunks = find_closest_chunks_bm25("insertion sort", pages, top_n=3)
# [print("\n",i) for i in chunks]

if __name__ == "__main__":
  import nltk
  from transformers import AutoTokenizer
  
  tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/multi-qa-MiniLM-L6-cos-v1")
  text = ("""A binary heap (min-heap for priority queue) can be implemented as an array. Insert: O(log n) (heapify up), Delete minimum (or maximum): O(log n) (heapify down), Find minimum: O(1) (root of the heap).""")
  print(get_cst_token_chunks(text, tokenizer, chunk_size=10, chunk_overlap=2))