import streamlit as st
from openai import OpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import create_retrieval_chain
from langchain.chains import create_history_aware_retriever
from langchain_core.prompts import MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain.chains.combine_documents import create_stuff_documents_chain
import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage
from utils.chunk_doc import get_retriever
from operator import itemgetter

os.environ['LANGCHAIN_TRACING_V2'] = 'true'
os.environ['LANGCHAIN_ENDPOINT'] = 'https://api.smith.langchain.com'
os.environ['LANGCHAIN_API_KEY']= st.secrets["EXTRA_Langchain_key"]
os.environ['LANGCHAIN_PROJECT']="chatbot-test"

# Initialize the LLM
llm = ChatOpenAI(
    model="gpt-4o-mini",
    # api_key=os.environ.get("OPENAI_API_KEY"),
    api_key=st.secrets["OpenAI_key"]
)

from langchain_ollama import OllamaLLM
gemmallm = OllamaLLM(model="gemma2:2b", base_url="http://localhost:11434")

retriever = get_retriever()

# Initial prompt to gauge user competency in DSA
initial_prompt = """
You are a DSA (Data Structures and Algorithms) assistant. Start by asking the user a few questions to gauge their familiarity and comfort level with DSA. Based on their responses, determine their competency level as 'beginner', 'intermediate', or 'advanced'.

Ask about:
- Familiarity with basic data structures (arrays, linked lists, stacks, queues)
- Understanding of sorting algorithms (e.g., insertion sort, merge sort)
- Experience with advanced topics (e.g., trees, graphs, dynamic programming)

Respond with a sentence indicating their level of competency. For example: "Based on your responses, I would classify your DSA competency level as 'beginner'."
"""
# Initial Chain to gauge competency
initial_chain = (
    {
        "input": itemgetter("input")
    }
    | ChatPromptTemplate.from_messages(
        [
            ("system", initial_prompt),
            ("human", "{input}"),
        ]
    )
    | llm
    | StrOutputParser()
)

# Function to determine user's level and store it in session state
def determine_user_level():
    if "user_level" not in st.session_state:
        user_level_response = initial_chain.invoke({"input": "Can you tell me about your experience with DSA?"})
        # st.session_state["user_level"] = user_level_response["message"]
        print(user_level_response)

# Contextual prompt that adapts explanations based on user level
def get_system_prompt():
    user_level = st.session_state.get("user_level", "beginner")  # Default to beginner if level is not set
    return f"""
    You are an assistant specializing in Data Structures and Algorithms (DSA) with an adaptive explanation style.
    The user's DSA competency level is {user_level}. Tailor your explanations to match this level.
    
    Only answer questions directly related to DSA topics or coding implementations.
    If the question is not specifically about DSA, politely redirect to discuss DSA topics.
    """

# Create the final QA chain using RAG (retrieval augmented generation) adapted to user level
competency_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", get_system_prompt()),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ]
)

competency_chain = (
    {
        "context": competency_prompt,
        "chat_history": itemgetter("chat_history"),
        "input": itemgetter("input"),
    }
    | competency_prompt
    | llm
    | StrOutputParser()
)

### Contextualize question ###
contextualize_q_system_prompt = (
    "Given a chat history and the latest user question "
    "which might reference context in the chat history, "
    "formulate a standalone question which can be understood "
    "without the chat history. Do NOT answer the question, "
    "just reformulate it if needed and otherwise return it as is."
)

contextualize_q_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", contextualize_q_system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ]
)

# Create contextual retrieval chain
contextual_query_chain = (
    {
        "chat_history": itemgetter("chat_history"),
        "input": itemgetter("input")
    }
    | contextualize_q_prompt
    | llm
    | StrOutputParser()
)

# retriever_chain = contextual_query_chain | retriever

# Multi Query Prompt Template
template = """You are an AI language model assistant. Your task is to generate five 
different versions of the given user question to retrieve relevant documents from a vector 
database. By generating multiple perspectives on the user question, your goal is to help
the user overcome some of the limitations of the distance-based similarity search. 
Provide these alternative questions separated by a single newline. Original question: {input}"""
prompt_perspectives = ChatPromptTemplate.from_template(template)

generate_queries = (
    prompt_perspectives
    | gemmallm
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

retriever_chain = generate_queries | retriever.map() | get_unique_union

### Answer question
system_prompt = (
    "You are an assistant specializing in Data Structures and Algorithms (DSA) and code implementations. Only answer questions that are directly related to DSA topics or involve code implementations. "
    "If the question is not specifically about DSA or programming code, redirect to talk more about DSA topics, even if relevant context is available. "
    "If the answer is not in the context, redirect to talk more about the topic. "
    "\n\n{context}"
)

qa_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ]
)

rag_chain = (
    {
        "context": retriever_chain,
        "chat_history": itemgetter("chat_history"),
        "input": itemgetter("input"),
    }
    | qa_prompt
    | llm
    | StrOutputParser()
)

st.title("DSA Chatbot")

# Add sidebar options
st.sidebar.title("Options")
if st.sidebar.button("Clear Chat History"):
    st.session_state["llm_chat_history"] = []
    st.session_state.messages = []
    
# Add file uploader to sidebar
uploaded_file = st.sidebar.file_uploader("Upload Files (Not Done)", type=["txt", "pdf", "docx"])

# Process the uploaded file if available
if uploaded_file is not None:
    file_details = {
        "filename": uploaded_file.name,
        "filetype": uploaded_file.type,
        "filesize": uploaded_file.size
    }
    st.sidebar.write("File Details:", file_details)
    # Process file content if needed; for example, reading and displaying content:
    if uploaded_file.type == "text/plain":
        file_content = uploaded_file.read().decode("utf-8")
        st.sidebar.write("File Content:", file_content)
    # Processing for other file types below

# Initialize LLM chat history (for context handling)
if "llm_chat_history" not in st.session_state:
    st.session_state["llm_chat_history"] = []
    determine_user_level()  # Run only once to get competency level
    
llm_chat_history = st.session_state["llm_chat_history"]

# Set a default model
if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-4o-mini"

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input
if prompt := st.chat_input("What is up?"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)
        
# Display assistant response in chat message container
    with st.chat_message("assistant"):
        # Initialize an empty list to hold the streamed chunks
        stream = []
        
        # if not llm_chat_history:
        #     for chunk in initial_chain.stream({"input": prompt}):
        #         stream.append(chunk)
        #     # Join the list of chunks to form the complete response
        #     full_response = st.write_stream(stream)
        # else:
        # Stream the response from the RAG chain for a specific input
        for chunk in initial_chain.stream({
            "input": prompt, 
            "chat_history": llm_chat_history
            }):
            # if answer_chunk := chunk.get("answer"):
            #     # Append the answer chunk to the stream list
            #     stream.append(answer_chunk)
            stream.append(chunk)

        # Join the list of chunks to form the complete response
        full_response = st.write_stream(stream)

        # Append the full response to the chat history
        llm_chat_history.extend(
            [
                HumanMessage(content=prompt),
                AIMessage(content=full_response),
            ]
        )

        # Display the full response in the chat message container
    st.session_state.messages.append({"role": "assistant", "content": full_response})