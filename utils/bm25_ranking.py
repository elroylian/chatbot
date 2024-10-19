from rank_bm25 import BM25Okapi
from nltk.tokenize import word_tokenize
from nltk.corpus import wordnet
import nltk
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

def get_top_synonyms(word, pos, top_n=3):
    # Initialize an empty set to store synonyms
    synonyms = set()
    # Get the synsets for the given word and part of speech
    synsets = wordnet.synsets(word, pos=pos)
    # Iterate over the top N synsets
    for syn in synsets[:top_n]:
        # Iterate over the lemmas in each synset
        for lemma in syn.lemmas():
            # Add the lemma name to the synonyms set
            synonyms.add(lemma.name())
    # Return the set of synonyms
    return synonyms
    

def expand_query(query, top_n_synonyms=1):
    # Split the query into words and initialize a set with these words
    expanded_query = set(query.split())
    # Map POS tags to WordNet POS tags
    pos_map = {'NN': 'n', 'VB': 'v', 'JJ': 'a', 'RB': 'r'}
    # Get the POS tags for the words in the query
    pos_tags = nltk.pos_tag(query.split())
    
    # Iterate over the words and their POS tags
    for word, tag in pos_tags:
        # Get the corresponding WordNet POS tag
        pos = pos_map.get(tag[:2], None)
        if pos:
            # Get the top N synonyms for the word
            synonyms = get_top_synonyms(word, pos, top_n_synonyms)
            # Add the synonyms to the expanded query set
            expanded_query.update(synonyms)
    # Return the expanded query as a list
    return list(expanded_query)
		

def find_closest_chunks_bm25(query, chunks, top_n=12):
    # Tokenize the chunks and prepare data
    tokenized_chunks = [word_tokenize(chunk) for chunk in chunks["documents"]]

    # Initialize BM25Okapi
    bm25 = BM25Okapi(tokenized_chunks)

    # Tokenize the query
    tokenized_query = word_tokenize(query)

    # Get document scores
    doc_scores = bm25.get_scores(tokenized_query)

    # Combine scores with chunks and metadata
    chunk_info = zip(doc_scores, chunks["documents"], chunks["ids"], chunks["metadatas"])

    # Sort by score in descending order and get top N
    top_chunks = sorted(chunk_info, key=lambda x: x[0], reverse=True)[:top_n]

    return [{"document": document, "score": score, "id": chunk_id, "source": metadata["source"]}
            for score, document, chunk_id, metadata in top_chunks]

	
def new_bm25(query, chunks, top_n=12):
 	# Tokenize the chunks and prepare data
    tokenized_chunks = [word_tokenize(chunk) for chunk in chunks["documents"]]

    # Initialize BM25Okapi
    bm25 = BM25Okapi(tokenized_chunks)

    # Tokenize the query
    tokenized_query = word_tokenize(query)

    # Get document scores
    doc_scores = bm25.get_scores(tokenized_query)

    # Combine scores with chunks and metadata
    chunk_info = zip(doc_scores, chunks["documents"], chunks["ids"], chunks["metadatas"])

    # Sort by score in descending order and get top N
    top_chunks = sorted(chunk_info, key=lambda x: x[0], reverse=True)[:top_n]

    return list(top_chunks)

def re_rank_chunks_with_embeddings(query, top_chunks):
    # Load pre-trained embedding model
    model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

    # Generate embeddings for the query
    query_embedding = model.encode(query).reshape(1, -1)

    # Generate embeddings for the top N chunks
    chunk_embeddings = [model.encode(chunk[1]) for chunk in top_chunks]

    # Calculate cosine similarity between the query and each chunk
    similarities = cosine_similarity(query_embedding, chunk_embeddings)[0]

    # Combine similarity scores with top chunks
    enhanced_chunks = [
        {
            "document": chunk[1],
            "bm25_score": chunk[0],
            "embedding_score": similarities[i],
            "id": chunk[2],
            "source": chunk[3]["source"]
        }
        for i, chunk in enumerate(top_chunks)
    ]

    # Sort by embedding similarity in descending order
    final_chunks = sorted(enhanced_chunks, key=lambda x: x["embedding_score"], reverse=True)

    # Print and return final top chunks
    for chunk in final_chunks:
        print(f"Chunk ID: {chunk['id']}, BM25 Score: {chunk['bm25_score']}, Embedding Score: {chunk['embedding_score']}, Source: {chunk['source']}")
        print(chunk["document"])

    return final_chunks