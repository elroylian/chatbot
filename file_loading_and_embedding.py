import asyncio
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter as Rec
from langchain_huggingface import HuggingFaceEmbeddings
from sklearn.metrics.pairwise import cosine_similarity
from transformers import AutoTokenizer, AutoModel
from utils.sentence_chunking import get_sentence_chunks
import numpy as np

async def load_pages():
    file_path = r"data/books/cp1.pdf"
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

embeddings_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")

# import chromadb
# CHROMA_PATH = "chroma"

# # Create a new DB from the documents
# chroma_client = chromadb.Client()
# db = chroma_client.fr

# Running the async function
if __name__ == "__main__":
    pages = asyncio.run(load_pages())
    print(pages[20])
    # Combine all page content into a single text
    # combined_text = "\n".join(pages)  # You can use "\n" instead of " " if you want to keep pages separate by newlines
    # # chunks = text_splitter.split_documents(pages)
    # # Initialize a tokenizer from transformers (you can replace this with the tokenizer you use)
    # tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/multi-qa-MiniLM-L6-cos-v1")
    # model = AutoModel.from_pretrained("sentence-transformers/multi-qa-MiniLM-L6-cos-v1")
    # # Call the function to get sentence chunks
    # chunks = get_sentence_chunks(combined_text, tokenizer, min_chunk_size=200, max_chunk_size=250, chunk_overlap=True)
    # # Encode the query
    # input_text = "What is competitive programming?"
    # encoded_input = tokenizer(input_text, return_tensors='pt')
    
    # print(f"\nThis is the start:\n",chunks[1])
    
    # embeddings = embeddings_model.embed_documents(chunks)
    # embedded_query = embeddings_model.embed_query("What is competitive programming?")
    
    # print(chunks[0])
    # Calculate cosine similarity
    # similarities = cosine_similarity([embedded_query], embeddings)[0]

    # # Sort documents by similarity
    # sorted_indices = np.argsort(similarities)[::-1]  # Sort in descending order

    # # Print the most similar documents
    # count = 0
    # for idx in sorted_indices:
    #     print(f"Chunk {idx}:\n",chunks[idx],"\nSimilarity: {similarities[idx]}\n\n")
    #     if(count<3):
    #         break
    #     count+=1
    
    # print(f"{pages[24].metadata}\n")
    # print(pages[24].page_content)
    # print(chunks[60])