import asyncio
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter as Rec
from langchain_huggingface import HuggingFaceEmbeddings
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

async def load_pages():
    file_path = r"C:/Users/elroy/OneDrive/Desktop/Personal/Elroy/chatbot/chatbot/introduction-to-algorithms-fixed.pdf"
    loader = PyPDFLoader(file_path)
    pages = []
    async for page in loader.alazy_load():
        pages.append(page)
    return pages

text_splitter = Rec(
    chunk_size=1000,
    chunk_overlap=500,
    length_function=len,
    add_start_index=True
)

embeddings_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
embeddings = embeddings_model.embed_documents(
    [
        "Einstein was born on March 14, 1879",
        "Oh, hello!",
        "What's your name?",
        "My friends call me World",
        "Hello World!"
    ]
)

embedded_query = embeddings_model.embed_query("When was Einstein's birthday?")

# Calculate cosine similarity
similarities = cosine_similarity([embedded_query], embeddings)[0]

# Sort documents by similarity
sorted_indices = np.argsort(similarities)[::-1]  # Sort in descending order

# Print the most similar documents
for idx in sorted_indices:
    print(f"Similarity: {similarities[idx]}\n")
    
# import chromadb
# CHROMA_PATH = "chroma"

# # Create a new DB from the documents
# chroma_client = chromadb.Client()
# db = chroma_client.fr

# Running the async function
# if __name__ == "__main__":
#     pages = asyncio.run(load_pages())
#     chunks = text_splitter.split_documents(pages)
#     # print(f"{pages[24].metadata}\n")
#     # print(pages[24].page_content)
#     print(chunks[60])