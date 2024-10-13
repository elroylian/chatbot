import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import wordnet
from utils.rank_bm25 import BM25Okapi
import numpy as np

# # Download required NLTK data
# nltk.download('punkt')
# nltk.download('wordnet')
# nltk.download('punkt_tab')

def find_closest_chunks_bm25(query, chunks, top_n=12):
    # tokenized_chunks = [word_tokenize(chunk.page_content) for chunk in chunks]
    tokenized_chunks = [word_tokenize(chunk) for chunk in chunks]
    
    # Initialize BM25Okapi
    bm25 = BM25Okapi(tokenized_chunks)
    
    # Tokenize the query
    tokenized_query = word_tokenize(query)
    
    # Get document scores
    doc_scores = bm25.get_scores(tokenized_query)
    
    # Sort the documents by score
    sorted_indices = np.argsort(doc_scores)[::-1]
    
    # Get the top N chunks
    top_chunks = [chunks[idx] for idx in sorted_indices[:top_n]]
    
    return top_chunks
