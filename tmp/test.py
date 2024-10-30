import chromadb
from sentence_transformers import SentenceTransformer

client = chromadb.PersistentClient(path="db/pdfs")
md_collection = client.get_or_create_collection("markdown_chunks_collection")

#Load the model
model = SentenceTransformer('sentence-transformers/multi-qa-MiniLM-L6-cos-v1')

# sentence = model.encode("How does the insertion sort algorithm work?")

results2 = md_collection.get()

from utils.bm25_ranking import find_closest_chunks_bm25

results_top_n = find_closest_chunks_bm25("How does the insertion sort algorithm work?", results2, top_n=5)

for res in results_top_n:
    print(res['id']+"\n")


# for result in results_top_n:
#     print(result["id"], result["score"], result["source"])
#     # print(result["document"])
#     print("\n")
    
