# This is a test file for DSA Chatbot before adding the code to the app.py file


import streamlit as st
from langchain_core.output_parsers import StrOutputParser
import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage
from utils.chunk_doc import get_retriever
from prompt_templates.contextual_query import get_context_query_chain
from prompt_templates.qa_template import get_qa_prompt
from prompt_templates.intial_template import get_initial_chain
from operator import itemgetter
import json
import re
import sqlite3

# Set up the SQLite database connection
conn = sqlite3.connect("chat_history.db")
c = conn.cursor()

# Initialize user session with user ID and chat ID
if "user_id" not in st.session_state:
    st.session_state["user_id"] = "2200499"  # Replace with real user ID as needed
if "chat_id" not in st.session_state:
    st.session_state["chat_id"] = "1"  # Unique identifier for each chat session
    
user_id = st.session_state["user_id"]
chat_id = st.session_state["chat_id"]

# Create chat history table if it doesn't exist
c.execute('''
CREATE TABLE IF NOT EXISTS chat_history (
    user_id TEXT,
    chat_id TEXT,
    role TEXT,
    content TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')
conn.commit()

# Function to save message to database
def save_message(user_id, chat_id, role, content):
    c.execute(
        "INSERT INTO chat_history (user_id, chat_id, role, content) VALUES (?, ?, ?, ?)",
        (user_id, chat_id, role, content),
    )
    conn.commit()

# Function to load chat history
def load_chat_history(user_id, chat_id):
    c.execute(
        "SELECT role, content, timestamp FROM chat_history WHERE user_id = ? AND chat_id = ? ORDER BY timestamp",
        (user_id, chat_id),
    )
    raw_history = c.fetchall()
    
    # Convert tuples to expected format for chat history
    formatted_history = [{"role": role, "content": content,"timestamp": timestamp} for role, content, timestamp in raw_history]
    return formatted_history

####       ####
#### TO DO ####
####       ####
# Refine prompt chain to ensure LLM explain based on User's competency level
# Restrict User from entering prompt when LLM is processing

os.environ['LANGCHAIN_TRACING_V2'] = 'true'
os.environ['LANGCHAIN_ENDPOINT'] = 'https://api.smith.langchain.com'
os.environ['LANGCHAIN_API_KEY']= st.secrets["New_Langsmith_key"]
os.environ['LANGCHAIN_PROJECT']="default"

# Define chatbot version for easier tracking
chatbot_version = "1.0.2"

# Initialize the LLM
llm = ChatOpenAI(
    model="gpt-4o-mini",
    # api_key=os.environ.get("OPENAI_API_KEY"),
    api_key=st.secrets["OpenAI_key"],
    temperature=0
)

# Initialize LLM chat history (for context handling)
if "llm_chat_history" not in st.session_state:
    st.session_state["llm_chat_history"] = []
    # st.session_state["llm_chat_history"] = load_chat_history(user_id, chat_id)

llm_chat_history = st.session_state["llm_chat_history"]

# Set a default model
if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-4o-mini"

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Initialize user level
if "user_level" not in st.session_state:
    st.session_state["user_level"] = ""
user_level = st.session_state["user_level"]

retriever = get_retriever()

contextual_query_chain = get_context_query_chain(llm)
retriever_chain = contextual_query_chain | retriever

qa_prompt = get_qa_prompt()
rag_chain = (
    {
        "context": retriever_chain,
        "user_level": itemgetter("user_level"),
        "chat_history": itemgetter("chat_history"),
        "input": itemgetter("input"),
    }
    | qa_prompt
    | llm
    | StrOutputParser()
)

initial_chain = get_initial_chain(llm)

st.title("DSA Chatbot (Test)")

# Add sidebar options
st.sidebar.title("Options")
st.sidebar.write("Version:", chatbot_version)
if st.sidebar.button("Clear Chat History"):
    st.session_state["llm_chat_history"] = []
    st.session_state.messages = []
    c.execute("DELETE FROM chat_history WHERE user_id = ? AND chat_id = ?", (user_id, chat_id))
    conn.commit()

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

# Display chat messages from history on app rerun
# for message in st.session_state.messages:
#     with st.chat_message(message["role"]):
#         st.markdown(message["content"])

# Display previous chat messages from history on app rerun
# for role, content, timestamp in st.session_state["llm_chat_history"]:
#     with st.chat_message(role):
#         st.markdown(f"{content}")
#         print(f"{content}")

####                ####
#### For debugging  ####
####                ####
def check_user_level():
    if st.session_state["user_level"] == "":
       print("############### User level is None")
    else:
        print("############### User level is not None")

# Accept user input
if prompt := st.chat_input("What is an Array?"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    save_message(user_id, chat_id, "user", prompt)
    
    print("###############\n")
    print(st.session_state.messages)
    print("###############\n")
    print(load_chat_history(user_id, chat_id))
    
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        
        # Initialize an empty list to hold the streamed chunks
        stream = []

        if st.session_state["user_level"] == "":
            
            print("RAN INITIAL CHAIN")
            
            response = initial_chain.invoke({
                "input": prompt,
                "chat_history": llm_chat_history
            })
            
            print("this is the response:\n",response)
            
            if "{" in response and "}" in response:
                try:
                    json_str = response[response.index("{"):response.rindex("}") + 1]
                    data = json.loads(json_str)

                    # Extract necessary fields
                    user_level = data.get("data").get("user_level")

                    # Extract message from LLM
                    message = data.get("message")
                    
                    # Append and save assistant's message
                    save_message(user_id, chat_id, "assistant", message)
                    
                    llm_chat_history.extend(
                        [
                            HumanMessage(content=prompt),
                            AIMessage(content=message),
                        ]
                    )
                    stream_message = re.findall(r'\S+|\s+', message)
                    full_response = st.write_stream(stream_message)
                    
                    # Display the full response in the chat message container
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                    
                    # Validate that necessary information is available
                    if user_level:
                        print("###############!!! User level is: ", user_level)
                        st.session_state["user_level"] = user_level

                except json.JSONDecodeError:
                    print(response)
                    print("Oops! I broke. Sorry about that!")
            else:
                print("Oops! I broke. Sorry about that! JSON FAILED")
                st.write(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
                # Append and save assistant's message
                save_message(user_id, chat_id, "assistant", response)
                llm_chat_history.extend(
                    [
                        HumanMessage(content="Remember, you MUST generate a syntactically correct JSON object."),
                        AIMessage(content=response),
                    ]
                )
        else:
          # Stream the response from the RAG chain for a specific input
            for chunk in rag_chain.stream({
              "input": prompt,
              "chat_history": llm_chat_history,
                "user_level": user_level
              }):
              # if answer_chunk := chunk.get("answer"):
              #     # Append the answer chunk to the stream list
              #     stream.append(answer_chunk)
              stream.append(chunk)

            # Join the list of chunks to form the complete response
            full_response = st.write_stream(stream)
            save_message(user_id, chat_id, "assistant", full_response)

            # Append the full response to the chat history
            llm_chat_history.extend(
                [
                    HumanMessage(content=prompt),
                    AIMessage(content=full_response),
                ]
            )

            # Display the full response in the chat message container
            st.session_state.messages.append({"role": "assistant", "content": full_response})