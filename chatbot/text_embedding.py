from sentence_transformers import SentenceTransformer
from langchain_huggingface import HuggingFaceEmbeddings


input = ["I am a happy person"]
sentences = ["That is a happy dog", "That is a very happy person","Today is a sunny day"]

model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
# model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
# embeddings = model.encode(sentences)
# input_embeddings = model.encode(input)
# similarities = model.similarity(input_embeddings, embeddings)
# print(similarities)



# model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
# embeddings = model.encode(sentences)
# input_embeddings = model.encode(input)
# similarities = model.similarity(input_embeddings, embeddings)
# print(similarities)

