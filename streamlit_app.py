import streamlit as st
from openai import OpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import create_retrieval_chain
from langchain.chains import create_history_aware_retriever
from langchain_core.prompts import MessagesPlaceholder
from langchain.chains.combine_documents import create_stuff_documents_chain
import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage
from utils.init import get_retriever

# Initialize the LLM
llm = ChatOpenAI(
    model="gpt-4o-mini",
    # api_key=os.environ.get("OPENAI_API_KEY"),
    api_key=st.secrets["OpenAI_key"]
)

# from langchain_ollama import OllamaLLM
# llm = OllamaLLM(model="gemma2:2b", base_url="http://localhost:11434")

retriever = get_retriever()
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

history_aware_retriever = create_history_aware_retriever(
    llm, retriever, contextualize_q_prompt
)

### Answer question
system_prompt = (
    "You are an Data Structure & Algorithms(DSA) assistant for question-answering tasks. "
    "Use the following pieces of retrieved context to answer "
    "the question. If the answer is not in the retrieved context,"
    "say that you don't know. If you do not understand the question"
    "or need more context, ask for clarification."
    # "Use three sentences maximum and keep the answer concise."
    "\n\n"
    "{context}"
)

qa_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ]
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
        
        # Create a chain of components to process the input
        question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
        rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)
        
        # Stream the response from the RAG chain for a specific input
        for chunk in rag_chain.stream({"input": prompt, "chat_history": llm_chat_history}):
            if answer_chunk := chunk.get("answer"):
                # Append the answer chunk to the stream list
                stream.append(answer_chunk)

        # Join the list of chunks to form the complete response
        full_response = st.write_stream(stream)

        # Append the full response to the chat history
        llm_chat_history.extend(
            [
                HumanMessage(content=prompt),
                AIMessage(content=full_response),
            ]
        )
        print(llm_chat_history)
        # Display the full response in the chat message container
    st.session_state.messages.append({"role": "assistant", "content": full_response})