from langchain_core.prompts import ChatPromptTemplate
from langchain_chroma import Chroma
from langchain.embeddings.base import Embeddings
from typing import List
import os
import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_ollama import OllamaLLM
from sentence_transformers import SentenceTransformer

class MyEmbeddings(Embeddings):
        def __init__(self):
            self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    
        def embed_documents(self, texts: List[str]) -> List[List[float]]:
            return [self.model.encode(t).tolist() for t in texts]
        
        def embed_query(self, query: str) -> List[float]:
            return self.model.encode(query).tolist()

embedding_func = MyEmbeddings()


# Multi Query: Different Perspectives
template = """You are an AI language model assistant. Your task is to generate five 
different versions of the given user question to retrieve relevant documents from a vector 
database. By generating multiple perspectives on the user question, your goal is to help
the user overcome some of the limitations of the distance-based similarity search. 
Provide these alternative questions separated by a single newline. Original question: {question}"""
prompt_perspectives = ChatPromptTemplate.from_template(template)

from langchain_core.output_parsers import StrOutputParser

gpt4 = ChatOpenAI(
    model="gpt-4o-mini",
    # api_key=os.environ.get("OPENAI_API_KEY"),
    api_key=st.secrets["OpenAI_key"],
    temperature=0
)

# llm = OllamaLLM(model="gemma2:2b", base_url="http://localhost:11434")
# llm = OllamaLLM(model="gemma2:2b", base_url="http://localhost:11434")

generate_queries = (
    prompt_perspectives 
    | gpt4
    | StrOutputParser() 
    | (lambda x: [line for line in x.split("\n") if line.strip() != ""])  # Ensure empty strings are removed
)

from langchain.load import dumps, loads

def get_unique_union(documents: list[list]):
    """ Unique union of retrieved docs """
    # Flatten list of lists, and convert each Document to string
    flattened_docs = [dumps(doc) for sublist in documents for doc in sublist]
    # Get unique documents
    unique_docs = list(set(flattened_docs))
    # Return
    return [loads(doc) for doc in unique_docs]

# Initialize ChromaDB client
vector_store = Chroma(
    # client = client,
    collection_name="markdown_chunks_collection",
    embedding_function=embedding_func,
    persist_directory = "../db/pdfs",
    # other params...
)

retriever = vector_store.as_retriever()

# Retrieve
question = "What is Insertion Sort?"
retrieval_chain = generate_queries | retriever.map() | get_unique_union
docs = retrieval_chain.invoke({"question":question})
# print(docs)
len(docs)

from operator import itemgetter

# RAG
template = """Answer the following question based on this context:

{context}

Question: {question}
"""

prompt = ChatPromptTemplate.from_template(template)

final_rag_chain = (
    {"context": retrieval_chain, 
     "question": itemgetter("question")} 
    | prompt
    | gpt4
    | StrOutputParser()
)

final_rag_chain.invoke({"question":question})
