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
from prompt_templates.contextual_query import get_context_query_chain
from prompt_templates.qa_template import get_qa_prompt
from operator import itemgetter

os.environ['LANGCHAIN_TRACING_V2'] = 'true'
os.environ['LANGCHAIN_ENDPOINT'] = 'https://api.smith.langchain.com'
os.environ['LANGCHAIN_API_KEY_CHATBOT']= st.secrets["EXTRA_Langchain_key"]
os.environ['LANGCHAIN_PROJECT']="chatbot-test"

# Initialize the LLM
llm = ChatOpenAI(
    model="gpt-4o-mini",
    # api_key=os.environ.get("OPENAI_API_KEY"),
    api_key=st.secrets["OpenAI_key"]
)

# from langchain_ollama import OllamaLLM
# llm = OllamaLLM(model="gemma2:2b", base_url="http://localhost:11434")


retriever = get_retriever()

contextual_query_chain = get_context_query_chain(llm)
retriever_chain = contextual_query_chain | retriever

qa_prompt = get_qa_prompt()
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
        
        # Stream the response from the RAG chain for a specific input
        for chunk in rag_chain.stream({
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