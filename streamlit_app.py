import yaml
import streamlit as st
from yaml.loader import SafeLoader
from model import llm_selected
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from utils.chunk_doc import get_retriever
from utils.document_processing import process_image, process_pdf
import json
import re
import os

import streamlit_authenticator as stauth
from streamlit_authenticator.utilities import (LoginError, RegisterError,)
from utils.db_connection import ChatDatabase
from langchain_core.messages import HumanMessage
from utils.level_manager import should_analyze_user_level, get_next_level, get_previous_level

## TO DO
# Check llm_chat_history there may be some issue with it when updating the state of the graph (x)
# Make upload file as st fragment ()

CHATBOT_VERSION = "1.4.2"
DB_FILENAME = "chat.db"

os.environ['LANGCHAIN_TRACING_V2'] = 'true'
os.environ['LANGCHAIN_ENDPOINT'] = 'https://api.smith.langchain.com'
os.environ['LANGCHAIN_API_KEY']= st.secrets["New_Langsmith_key"]
os.environ['LANGCHAIN_PROJECT']="default"

# Loading config file
with open('config.yaml', 'r', encoding='utf-8') as file:
    auth_config = yaml.load(file, Loader=SafeLoader)
    
# Creating the authenticator object
authenticator = stauth.Authenticate(
    auth_config['credentials'],
    auth_config['cookie']['name'],
    auth_config['cookie']['key'],
    auth_config['cookie']['expiry_days']
)

#####################################
from test_templates.memory import memory
from test_templates.intial_template import workflow
from test_templates.document_text_template import document_text_workflow
from test_templates.text_template import text_workflow
from utils.analyser import analyser_workflow

langgraph_config = {"configurable": {"thread_id": "1"}}

initial_graph = workflow.compile(checkpointer=memory)
document_text_graph = document_text_workflow.compile(memory)
text_graph = text_workflow.compile(memory)
analyser_graph = analyser_workflow.compile()

print("Initialising the app...\n")
##########################################
# Initialize the LLM
llm = llm_selected

# Initialize the database manager
@st.cache_resource
def get_database():
    return ChatDatabase(DB_FILENAME)

db = get_database()

def clear_session():
    # Reset chat history when user logs out
    print("Clearing session variables")
    session_vars = ["messages", "llm_chat_history", "user_level"]
    for var in session_vars:
        if var in st.session_state:
            del st.session_state[var]


st.title("💬DSA Chatbot")        

if st.session_state["authentication_status"] is None or st.session_state["authentication_status"] is False:
    
    clear_session()
    
    # Create tabs for login and registration
    tab1, tab2 = st.tabs(["Login", "Register"])

    # Login Tab
    with tab1:            
        # Creating a login widget
        try:
            authenticator.login('main')

        except LoginError as e:
            st.error(e)
        
        if st.session_state["authentication_status"] is False:
            st.error('Username/password is incorrect')
        elif st.session_state["authentication_status"] is None:
            st.warning('Please enter your username and password')

    # Registration Tab
    with tab2:
        # Creating a new user registration widget
        try:
            (email_of_registered_user,
            username_of_registered_user,
            name_of_registered_user) = authenticator.register_user(roles=["user"])
            if email_of_registered_user:
                generated_id = db.generate_user_id()
                db.save_user_data(generated_id, "", email_of_registered_user)
                
                # Saving config file
                with open('config.yaml', 'w', encoding='utf-8') as file:
                    yaml.dump(auth_config, file, default_flow_style=False)
                
                st.success('User registered successfully')
                st.info('Please proceed to login')

        except RegisterError as e:
            st.error(e)
else:
    if st.session_state["authentication_status"]:

        st.sidebar.write("Welcome, ",st.session_state['name'])
        authenticator.logout('Logout','sidebar')
        st.sidebar.write("Version:", CHATBOT_VERSION)
        
        # Initialize session variables
        if "messages" not in st.session_state:
            st.session_state["messages"] = []
        
        
        # Load user info from the database
        if user_info := db.get_user_by_email(st.session_state['email']):
            
            # ChatID & User Info
            chat_id = user_info['user_id']+"_1"
            user_id = user_info['user_id']
            user_email = user_info['email']
            
            # Load chat history upon successful login
            user_info = db.get_user_by_email(st.session_state['email'])
            chat_id = f"{user_info['user_id']}_1"
            chat_history = db.load_chat_history(user_info['user_id'], chat_id)
            
            # If chat history exists, load it into the messages list
            if chat_history:
                print("Loading Chat History...\n")
                if st.session_state["messages"] == []:
                    print("Appending Chat History...\n")
                    for message in chat_history:
                        if message["role"] == "user":
                            st.session_state["messages"].append(HumanMessage(content=message["content"]))
                        else:
                            st.session_state["messages"].append(AIMessage(content=message["content"]))
                    
                    initial_graph.update_state(values = {"messages": st.session_state["messages"]}, config = langgraph_config)
            
            llm_chat_history = st.session_state["messages"]
            
            # Initialize user level
            st.session_state["user_level"] = db.get_user_level(user_id)
            
            if st.session_state["user_level"]:
                user_level = st.session_state["user_level"]
            else:
                st.session_state["user_level"] = ""
        else:
            st.error("User not found in the database.")
            st.stop()
            
        try:
            retriever = get_retriever()
        except Exception as e:
            st.error(f"An error occurred: {e}")
            clear_session()
            st.stop()
        
        # Add sidebar options
        st.sidebar.title("Options")
        
        # Clear chat history
        if st.sidebar.button("Clear Chat History"):
            # st.session_state["llm_chat_history"] = []
            st.session_state["messages"] = []
            
            updated_messages = []
            initial_graph.update_state(values = {"messages": updated_messages}, config = langgraph_config)
            db.clear_chat_history(user_id, chat_id)
            st.toast("Chat history cleared successfully.")

        # Add file uploader to sidebar based on user assessment status
        if st.session_state["user_level"] in ["", "null", None]:
            st.sidebar.warning("Complete your initial assessment to unlock file uploads. Start by asking a question in the chat.")
        else:
            if "uploader_key" not in st.session_state:
                st.session_state["uploader_key"] = 0
            
            def update_key():
                print("UPDATING KEY\n")
                st.session_state["uploader_key"] += 1
            
            uploaded_files = st.sidebar.file_uploader("Upload Files", 
                                                      type=["png", "jpg", "jpeg","pdf"], 
                                                      accept_multiple_files=True, 
                                                      key= st.session_state["uploader_key"]
                                                      )
            
            # To be passed as input to the LLM
            processed_images = []  # For base64 encoded images
            processed_text = []    # For text content from documents
            
            if uploaded_files:
                for uploaded_file in uploaded_files:
                    if uploaded_file.size > 5 * 1024 * 1024:  # 5MB limit
                        st.sidebar.error("File too large. Please upload a file smaller than 5MB")
                        continue
                        
                    else:
                        try:
                            # Handle different file types
                            if uploaded_file.type.startswith('image'):
                                base64_image, processed_image = process_image(uploaded_file)
                                st.sidebar.image(processed_image, caption="Processed Image")
                                processed_images.append(base64_image)
                                st.toast("Image uploaded successfully.")
                                
                            elif uploaded_file.type == 'application/pdf':
                                pdf_documents = process_pdf(uploaded_file)
                                for doc in pdf_documents:
                                    processed_text.append(doc)
                                st.sidebar.success(f"Processed PDF: {uploaded_file.name}")
                        except Exception as e:
                            st.sidebar.error(f"Error processing file {uploaded_file.name}: {str(e)}")
                                
        def tester_function():
            if "tester" in st.session_state['roles']:
                st.title("Extra Options:")
                st.write(db.get_user_by_email(st.session_state['email']))
                if st.button("Reset User Level", type='primary'):
                    db.save_user_data(user_info["user_id"], "", st.session_state['email'])
                    st.session_state["user_level"] = ""
                    st.success("User level reset successfully.")
        
        if "user_topics" in st.session_state and st.session_state["user_topics"]:
            st.sidebar.markdown("### Topics Covered")
            for parent_topic, subtopics in st.session_state["user_topics"].items():
                st.sidebar.markdown(f"**{parent_topic.capitalize()}**")
                for subtopic in subtopics:
                    st.sidebar.write(f"- {subtopic}")
 
        with st.sidebar:
            tester_function()
        
        # Display chat messages from history on app rerun
        if "messages" in st.session_state:
            for message in st.session_state.messages:
                with st.chat_message("user" if isinstance(message, HumanMessage) else "assistant"):
                    st.markdown(message.content)

        # Accept user input
        if prompt := st.chat_input("What is an Array?"):
            
            # Add user message to chat history
            st.session_state.messages.append(HumanMessage(content=prompt))
            db.save_message(user_id, chat_id, "user", prompt)
            
            # Display user message in chat message container
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Display assistant response in chat message container
            with st.chat_message("assistant"):
                
                # Initialize an empty list to hold the streamed chunks
                stream = []

                # Before processing user input, validate user level status
                if st.session_state["user_level"].lower() not in ["beginner", "intermediate", "advanced"]:
                    
                    # New user needs assessment
                    print("RAN INITIAL ASSESSMENT CHAIN\n")
                    
                    with st.spinner("Analysing your experience level..."):
                        input_dict = {
                            "messages": [HumanMessage(prompt)],
                        }
                        
                    output = initial_graph.invoke(input_dict, langgraph_config)
                    
                    response = output["messages"][-1].content
                    print("this is the response:\n",response)
                    
                    if "{" in response and "}" in response:
                        try:
                            json_str = response[response.index("{"):response.rindex("}") + 1]
                            
                            data = json.loads(json_str)

                            # Extract necessary fields
                            user_level = data.get("data").get("user_level")
                            db.save_user_data(user_id, user_level,user_email)

                            # Extract message from LLM
                            message = data.get("message")
                            
                            # Append and save assistant's message
                            db.save_message(user_id, chat_id, "assistant", message)

                            stream_message = re.findall(r'\S+|\s+', message)
                            full_response = st.write_stream(stream_message)
                            
                            # Display the full response in the chat message container
                            st.session_state.messages.append(AIMessage(content=full_response))
                            
                            # Validate that necessary information is available
                            if user_level:
                                print("###############!!! User level is: ", user_level)
                                st.session_state["user_level"] = user_level
                                
                                # Keep only the last assessment message
                                st.session_state["messages"] = [AIMessage(content=full_response)]
                                
                                # Clear assessment chat
                                initial_graph.update_state(values = {"messages": st.session_state["messages"]}, config = langgraph_config)
                                db.clear_chat_history(user_id, chat_id)
                                db.save_message(user_id, chat_id, "assistant", full_response)
                                
                                # Rerun the app
                                st.rerun()
                                

                        except json.JSONDecodeError:
                            print(response)
                            print("Oops! I broke. Sorry about that!")
                    else:
                        print("Oops! I broke. Sorry about that! JSON FAILED")
                        st.write(response)
                        # st.session_state.messages.append({"role": "assistant", "content": response})
                        st.session_state.messages.append(AIMessage(content=response))
                        # Append and save assistant's message
                        db.save_message(user_id, chat_id, "assistant", response)

                else:
                
                    with st.spinner("Thinking..."):                        
                        # Check if the user input contains any document (images or text from PDFs)
                        if processed_images or processed_text:
                            print("PROCESSING DOCUMENT QUERY\n\n")

                            # Format content with text and images
                            content = [{"type": "text", "text": prompt}]
                            
                            # Add each image to the content
                            for img in processed_images:
                                content.append({
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{img}"
                                    }
                                })
                            
                            # Handle PDF text content
                            pdf_context = ""
                            if processed_text:
                                # If processed_text is a string
                                if isinstance(processed_text, str):
                                    pdf_context = processed_text
                                # If processed_text is a list of strings
                                elif isinstance(processed_text, list) and all(isinstance(item, str) for item in processed_text):
                                    pdf_context = "\n\n".join(processed_text)
                                # For any other format, try to convert to string
                                else:
                                    pdf_context = str(processed_text)
                            
                            # Initialize state for image and text workflow
                            state = {
                                "messages": [HumanMessage(content=content)],
                                "user_level": user_level,
                                "pdf_context": pdf_context
                            }
                            
                            # Run the workflow
                            response = document_text_graph.invoke(state, langgraph_config)
                            
                            # Get the final message and handle response
                            final_message = response["messages"][-1].content
                            stream_message = re.findall(r'\S+|\s+', final_message)
                            full_response = st.write_stream(stream_message)
                            
                            # Save to database and update histories
                            db.save_message(user_id, chat_id, "assistant", full_response)
                            # llm_chat_history.extend([
                            #     HumanMessage(content=prompt),
                            #     AIMessage(content=full_response),
                            # ])
                            # st.session_state.messages.append({"role": "assistant", "content": full_response})
                            st.session_state.messages.append(AIMessage(content=full_response))

                            # Clear the uploaded files after processing
                            update_key()
                            # Also clear the processed_text and processed_images
                            processed_images = []
                            processed_text = []
                            st.rerun()
                        else:
                            print("PROCESSING NON-DOCUMENT QUERY\n")
                            
                            # Process the user input
    
                            inputs = {
                                "messages": [HumanMessage(prompt)],
                                "user_level": user_level
                            }
                            output = text_graph.invoke(inputs, langgraph_config)
                            response = output["messages"][-1].content
                            
                            st.session_state.messages.append(AIMessage(content=response))
                            
                            stream_message = re.findall(r'\S+|\s+', response)
                            full_response = st.write_stream(stream_message)
                            db.save_message(user_id, chat_id, "assistant", response)
        
            # After processing the user input and getting a response
            # Check if we should run level analysis
            if should_analyze_user_level(user_id):
                with st.spinner("Assessing your progress..."):
                    # Run the analyzer
                    previous_topics = db.get_user_topics(user_id)  # Ensure this returns a dictionary

                    analysis_input = {
                        "messages": llm_chat_history,
                        "user_level": user_level,
                        "previous_topics": previous_topics
                    }

                    analysis_result = analyser_graph.invoke(analysis_input, langgraph_config)
                    analysis_message = analysis_result["messages"][-1].content
                    
                    try:
                        # Extract the level assessment
                        # print(type(analysis_message))
                        # print(analysis_message)
                        
                        analysis_data = json.loads(analysis_message)
                        user_level = analysis_data.get("current_level")
                        topics = analysis_data.get("topics", {})
                        
                        # if analysis_data["recommendation"] == "Promote" and analysis_data["confidence"] >= 0.8:
                        #     # Map levels (assuming you have a mapping function)
                        #     new_level = get_next_level(user_level)
                        #     db.update_user_level(user_id, new_level)
                        #     st.session_state["user_level"] = new_level
                        #     st.success(f"Congratulations! You've been promoted to {new_level} level.")
                        
                        # elif analysis_data["recommendation"] == "Demote" and analysis_data["confidence"] >= 0.9:
                        #     # Higher confidence threshold for demotion
                        #     new_level = get_previous_level(user_level)
                        #     db.update_user_level(user_id, new_level)
                        #     st.session_state["user_level"] = new_level
                        #     st.info(f"Your level has been adjusted to {new_level}.")
                        
                        # Update the timestamp regardless of outcome
                        db.update_analysis_timestamp(user_id)
                        
                        # # Save user level and topics
                        db.save_user_data(user_id, user_level, user_email)
                        db.update_user_topics(user_id, topics)
                        
                    except (json.JSONDecodeError, KeyError) as e:
                        print(f"Error processing analysis result: {e}")
