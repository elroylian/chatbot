"""
Main Streamlit application file for the DSA Chatbot.
"""

import logging
import yaml
import streamlit as st
from yaml.loader import SafeLoader
from utils.model import get_llm
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from utils.chunk_doc import get_retriever
from utils.document_processing import process_image, process_pdf
import json
import re
import os
import time

import streamlit_authenticator as stauth
from streamlit_authenticator.utilities import (LoginError, RegisterError,)
from utils.db_connection import ChatDatabase
from langchain_core.messages import HumanMessage
from utils.level_manager import should_analyze_user_level, get_next_level, get_previous_level
from utils.topic_recommendation import get_topic_recommendations

## TO DO
# Error Handling ensure db does not save user message if there is an error in the response
# Timestamp will be later than AIMessage if user prompt is saved later


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

CHATBOT_VERSION = "2.3.0"
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

analyser_graph = analyser_workflow.compile()

##########################################
# Initialize the LLM
llm = get_llm()

# Initialize the database manager
@st.cache_resource
def get_database():
    return ChatDatabase(DB_FILENAME)

db = get_database()

cookie_session_available = authenticator.cookie_controller.get_cookie()

# Set default authentication status
if "authentication_status" not in st.session_state:
    st.session_state["authentication_status"] = None

if cookie_session_available:
    try:
        username = cookie_session_available["username"]
        user_data = db.get_user_by_username(username)
        
        if user_data:
            st.session_state["authentication_status"] = True
            roles = json.loads(user_data["roles"])
            st.session_state["roles"] = roles["roles"] 
            st.session_state["email"] = user_data["email"]
            st.session_state["username"] = user_data["username"]
        else:
            # User not found in database, clear cookie
            authenticator.cookie_controller.clear_cookie()
            st.session_state["authentication_status"] = None
            
            
    except Exception as e:
        st.error(f"Error loading user data: {e}")
        st.session_state["authentication_status"] = None

def clear_session():
    # Reset chat history when user logs out
    logger.info("Clearing session variables")
    session_vars = ["messages", "llm_chat_history", "user_level", "user_topics"]
    for var in session_vars:
        if var in st.session_state:
            del st.session_state[var]
            
def analyse_user_progress(user_id, llm_chat_history, user_level, langgraph_config):
    # with st.spinner("Assessing your progress...", show_time=True):
    st.toast('Assessing your progress...')
    
    try:
        # Get previous topics with error handling
        previous_topics = {}
        db_topics = db.get_user_topics(user_id)
        
        if db_topics:
            if isinstance(db_topics, dict):
                previous_topics = db_topics
            elif isinstance(db_topics, str):
                try:
                    previous_topics = json.loads(db_topics)
                except json.JSONDecodeError:
                    # If JSON is invalid, use empty dict
                    previous_topics = {}
        
        # Ensure previous_topics is a dictionary
        if not isinstance(previous_topics, dict):
            previous_topics = {}
        
        # Run the analyzer
        analysis_input = {
            "messages": llm_chat_history,
            "user_level": user_level,
            "previous_topics": previous_topics
        }

        analysis_result = analyser_graph.invoke(analysis_input, langgraph_config)
        analysis_message = analysis_result["messages"][-1].content
        
        try:
            # Extract the level assessment
            analysis_data = json.loads(analysis_message)
            user_level = analysis_data.get("current_level")
            topics = analysis_data.get("topics", {})
            
            # Ensure topics is a dictionary
            if not isinstance(topics, dict):
                topics = {}
            
            
            # Handle level changes            
            # analyse_test = True 
            # if analyse_test:
            if analysis_data.get("recommendation") == "Promote" and analysis_data.get("confidence", 0) >= 0.8:
                new_level = get_next_level(user_level)
                db.update_user_level(user_id, new_level)
                st.session_state["user_level"] = new_level
                st.toast(f"Congratulations! You've been promoted to {new_level} level.", icon="🎉")
                # st.success(f"Congratulations! You've been promoted to {new_level} level.")
            
            elif analysis_data.get("recommendation") == "Demote" and analysis_data.get("confidence", 0) >= 0.9:
                new_level = get_previous_level(user_level)
                db.update_user_level(user_id, new_level)
                st.session_state["user_level"] = new_level
                # st.info(f"Your level has been adjusted to {new_level}.")
                st.toast(f"Your level has been adjusted to {new_level}.", icon="🔁")
            
            
            # Update the timestamp
            db.update_analysis_timestamp(user_id)
            
            # Merge and save topics (instead of just replacing)
            merged_topics = merge_topics(previous_topics, topics)
            db.update_user_topics(user_id, merged_topics)
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing analysis message as JSON: {e}")
            logger.error(f"Raw message: {analysis_message}")
            
        except Exception as e:
            logger.error(f"Error processing analysis result: {e}", exc_info=True)
            
    except Exception as e:
        logger.error(f"Error in analyse_user_progress: {e}", exc_info=True)

# Helper function to merge topics
def merge_topics(existing_topics, new_topics):
    """
    Merge new topics with existing topics, preserving and combining subtopics.
    
    Args:
        existing_topics (dict or str): Dictionary of existing parent topics and their subtopics or JSON string
        new_topics (dict or str): Dictionary of new parent topics and their subtopics or JSON string
        
    Returns:
        dict: Merged topics dictionary
    """
    # Ensure existing_topics is a dictionary
    if existing_topics is None:
        existing_topics = {}
    elif isinstance(existing_topics, str):
        try:
            existing_topics = json.loads(existing_topics)
        except (json.JSONDecodeError, TypeError):
            existing_topics = {}
    
    # Ensure new_topics is a dictionary
    if new_topics is None:
        new_topics = {}
    elif isinstance(new_topics, str):
        try:
            new_topics = json.loads(new_topics)
        except (json.JSONDecodeError, TypeError):
            new_topics = {}
    
    # If after conversion, either is still not a dictionary, make it one
    if not isinstance(existing_topics, dict):
        existing_topics = {}
    if not isinstance(new_topics, dict):
        new_topics = {}
    
    # Now we can safely copy and merge
    merged = existing_topics.copy()
    
    for parent_topic, subtopics in new_topics.items():
        if parent_topic in merged:
            # Ensure subtopics is a list
            if not isinstance(subtopics, list):
                subtopics = [subtopics] if subtopics else []
            
            # Ensure merged[parent_topic] is a list
            if not isinstance(merged[parent_topic], list):
                merged[parent_topic] = [merged[parent_topic]] if merged[parent_topic] else []
            
            # Add only new subtopics
            existing_subtopics = set(merged[parent_topic])
            for subtopic in subtopics:
                if subtopic and subtopic not in existing_subtopics:
                    merged[parent_topic].append(subtopic)
        else:
            # Add the new parent topic with all its subtopics
            # Ensure subtopics is a list
            if not isinstance(subtopics, list):
                subtopics = [subtopics] if subtopics else []
            merged[parent_topic] = subtopics
    
    return merged

def user_level_display():
    current_level = st.session_state.user_level.capitalize()
    st.markdown(f"""
    <div style="margin-bottom: 1.5rem;">
        <span style="font-weight: 500;">Your current level:</span></br>
        <span style="background-color: #8c52ff; padding: 3px 10px; border-radius: 12px; font-weight: 600;">{current_level}</span>
    </div>
    """, unsafe_allow_html=True)
    

def auth_page():
    clear_session()
    
    st.title("🔒 Login and Registration")
    
    # Create tabs for login and registration
    tab1, tab2 = st.tabs(["Login", "Register"])

    # Login Tab
    with tab1:
        if st.session_state["authentication_status"] is False:
            st.error('Username/password is incorrect')
        elif st.session_state["authentication_status"] is None:
            st.warning('Please enter your username and password')
                    
        # Creating a login widget
        try:
            authenticator.login('main')

        except LoginError as e:
            st.error(e)
        
        

    # Registration Tab
    with tab2:
        # Creating a new user registration widget
        try:
            (email_of_registered_user,
            username_of_registered_user,
            _
            ) = authenticator.register_user(roles=["user"])
            if email_of_registered_user:
                generated_id = db.generate_user_id()
                db.save_user_data(generated_id, "", email_of_registered_user, username_of_registered_user, roles='{"roles":["user","tester"]}')
                
                # Saving config file
                with open('config.yaml', 'w', encoding='utf-8') as file:
                    yaml.dump(auth_config, file, default_flow_style=False)
                
                st.success('User registered successfully')
                st.info('Please proceed to login')

        except RegisterError as e:
            st.error(e)

def chatbot_page():
    st.title("💬DSA Chatbot")
    
    
    authenticator.login('unrendered',clear_on_submit=True)
    
    current_graph = workflow.compile(memory)
    
    # if st.session_state.get('authentication_status'):
    #     authenticator.logout('Logout','sidebar',key='main',callback=clear_session())
    
    # Initialize session variables
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
        
    if "user_id" not in st.session_state:
        st.session_state["user_id"] = ""
    
    # Load user info from the database
    if user_info := db.get_user_by_email(st.session_state['email']):
        
        # ChatID & User Info
        chat_id = user_info['user_id']+"_1"
        user_id = user_info['user_id']
        st.session_state["user_id"] = user_id
        user_email = user_info['email']
        
        # Load chat history upon successful login
        user_info = db.get_user_by_email(st.session_state['email'])
        chat_id = f"{user_info['user_id']}_1"
        chat_history = db.load_chat_history(user_info['user_id'], chat_id)
        
        # Initialize the language graph configuration
        langgraph_config = {"configurable": {"thread_id": user_id}}
        
        # If chat history exists, load it into the messages list
        if chat_history:
            if st.session_state["messages"] == []:
                for message in chat_history:
                    if message["role"] == "user":
                        st.session_state["messages"].append(HumanMessage(content=message["content"]))
                    else:
                        st.session_state["messages"].append(AIMessage(content=message["content"]))
                
                current_graph.update_state(values = {"messages": st.session_state["messages"]}, config = langgraph_config)
                
        
        llm_chat_history = st.session_state["messages"]
        
        # Initialize user level
        st.session_state["user_level"] = db.get_user_level(user_id)
        
        if st.session_state["user_level"]:
            user_level = st.session_state["user_level"]
        else:
            st.session_state["user_level"] = ""
            
        # Add file uploader to sidebar based on user assessment status
        if st.session_state["user_level"] in ["", "null", None]:
            st.info("Start chatting to complete your initial assessment.")
        
    else:
        st.error("User not found in the database.")
        st.stop()
        
    if st.session_state["user_level"].lower() in ["beginner", "intermediate", "advanced"]:
        # Add sidebar options
        with st.sidebar:
            st.markdown(f"<div style='margin-bottom: 15px;'><span style='font-weight: bold;'>Version:</span> <code>{CHATBOT_VERSION}</code></div>", unsafe_allow_html=True)
            st.text(f"Welcome, {st.session_state['username']}!")
        
        with st.sidebar:
            user_level_display()
            
        with st.sidebar:
            st.write("Options")
            # Clear chat history
            if st.button("Clear Chat History",type='primary'):
                # st.session_state["llm_chat_history"] = []
                
                st.session_state["messages"] = []
                # Reset all graph states
                memory.storage.clear()
                current_graph.update_state(values = {"messages": []}, config = langgraph_config)
                
                db.clear_chat_history(user_id, chat_id)
                st.toast("Chat history cleared successfully.",icon="✅")
                analyse_user_progress(user_id, llm_chat_history, user_level, langgraph_config)
                
                
            if "uploader_key" not in st.session_state:
                st.session_state["uploader_key"] = 0
            
            def update_key():
                st.session_state["uploader_key"] += 1
            
            uploaded_files = st.sidebar.file_uploader("Upload Files", 
                                                        type=["png", "jpg", "jpeg","pdf"], 
                                                        accept_multiple_files=True, 
                                                        key= st.session_state["uploader_key"],
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
                                st.toast("Image uploaded successfully.",icon="✅")
                                
                            elif uploaded_file.type == 'application/pdf':
                                pdf_documents = process_pdf(uploaded_file)
                                for doc in pdf_documents:
                                    processed_text.append(doc)
                                st.sidebar.success(f"Processed PDF: {uploaded_file.name}")
                        except Exception as e:
                            st.sidebar.error(f"Error processing file {uploaded_file.name}: {str(e)}")
                            
            def tester_function():
                if "tester" in st.session_state["roles"]:
                    st.sidebar.text("Debug Options (!!!):")
                    st.write(db.get_user_by_email(st.session_state['email']))
                    
                    # Test options
                    st.sidebar.subheader("Test Options")
                    
                    # Reset User Level
                    if st.sidebar.button("Reset User Level", type='primary'):
                        db.update_user_data(user_info["user_id"], "", st.session_state['email'])
                        st.session_state["user_level"] = ""
                        st.success("User level reset successfully.")
                    
                    # Test LLM Failures
                    st.sidebar.subheader("Test LLM Failures")
                    
                    # Test JSON parsing failure
                    if st.sidebar.button("Test JSON Parse Failure"):
                        st.session_state["test_failure"] = "json_parse"
                        st.info("Next message will simulate JSON parsing failure")
                    
                    # Test LLM timeout
                    if st.sidebar.button("Test LLM Timeout"):
                        st.session_state["test_failure"] = "timeout"
                        st.info("Next message will simulate LLM timeout")
                    
                    # Test LLM error response
                    if st.sidebar.button("Test LLM Error Response"):
                        st.session_state["test_failure"] = "error_response"
                        st.info("Next message will simulate LLM error response")
                    
                    # Clear test state
                    if st.sidebar.button("Clear Test State"):
                        st.session_state.pop("test_failure", None)
                        st.success("Test state cleared")

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
                logger.info("Running INITIAL ASSESSMENT CHAIN\n")
                
                with st.spinner("Analysing your experience level..."):
                    input_dict = {
                        "messages": [HumanMessage(prompt)],
                    }
                
                try:
                    current_graph = workflow.compile(memory)
                    output = current_graph.invoke(input_dict, langgraph_config)
                    response = output["messages"][-1].content
                    
                    if "{" in response and "}" in response:
                        try:
                            json_str = response[response.index("{"):response.rindex("}") + 1]
                            
                            data = json.loads(json_str)

                            # Extract necessary fields
                            user_level = data.get("data").get("user_level")
                            db.update_user_data(user_id, user_level,user_email)

                            # Extract message from LLM
                            message = data.get("message")
                            
                            # Now that we have a successful response, save both messages
                            db.save_message(user_id, chat_id, "user", prompt)
                            db.save_message(user_id, chat_id, "assistant", message)

                            stream_message = re.findall(r'\S+|\s+', message)
                            full_response = st.write_stream(stream_message)
                            
                            # Display the full response in the chat message container
                            st.session_state.messages.append(AIMessage(content=full_response))
                            
                            # Validate that necessary information is available
                            if user_level:
                                logger.info(f"User level determined: {user_level}")
                                st.session_state["user_level"] = user_level
                                
                                # Keep only the last assessment message
                                st.session_state["messages"] = [AIMessage(content="You may now ask your DSA question.")]
                                
                                db.clear_chat_history(user_id, chat_id)
                                # db.save_message(user_id, chat_id, "assistant", full_response)
                                
                                # Rerun the app
                                st.rerun()

                        except json.JSONDecodeError:
                            logger.error("Error parsing JSON response")
                            error_message = "I apologise, but I encountered an error processing the response. Please try asking your question again."
                            st.session_state.messages.append(AIMessage(content=error_message))
                            st.write_stream(re.findall(r'\S+|\s+', error_message))
                    else:
                        logger.error("No JSON data found in response")
                        error_message = "I apologise, but I couldn't process the response properly. Please try asking your question again."
                        st.session_state.messages.append(AIMessage(content=error_message))
                        st.write_stream(re.findall(r'\S+|\s+', error_message))
                except Exception as e:
                    logger.error(f"Error in assessment: {str(e)}")
                    error_message = "I apologise, but I encountered an error during the assessment. Please try again."
                    st.session_state.messages.append(AIMessage(content=error_message))
                    st.write_stream(re.findall(r'\S+|\s+', error_message))

            else:
                with st.spinner("Thinking...",show_time=False):                        
                    # Check if the user input contains any document (images or text from PDFs)
                    if processed_images or processed_text:
                        logger.info("Processing Document/Text Query")

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
                            if isinstance(processed_text, str):
                                pdf_context = processed_text
                            elif isinstance(processed_text, list) and all(isinstance(item, str) for item in processed_text):
                                pdf_context = "\n\n".join(processed_text)
                            else:
                                pdf_context = str(processed_text)
                        
                        try:
                            # Initialize state for image and text workflow
                            state = {
                                "messages": [HumanMessage(content=content)],
                                "user_level": user_level,
                                "pdf_context": pdf_context
                            }
                            
                            # Run the workflow
                            current_graph = document_text_workflow.compile(memory)
                            response = current_graph.invoke(state, langgraph_config)
                            
                            # Get the final message and handle response
                            final_message = response["messages"][-1].content
                            
                            # Now that we have a successful response, save both messages
                            db.save_message(user_id, chat_id, "user", prompt)
                            db.save_message(user_id, chat_id, "assistant", final_message)
                            
                            stream_message = re.findall(r'\S+|\s+', final_message)
                            full_response = st.write_stream(stream_message)
                            
                            # Update session state
                            st.session_state.messages.append(AIMessage(content=full_response))

                            # Clear the uploaded files after processing
                            update_key()
                            # Also clear the processed_text and processed_images
                            processed_images = []
                            processed_text = []
                            st.rerun()
                        except Exception as e:
                            logger.error(f"Error processing document: {str(e)}")
                            error_message = "I apologize, but I encountered an error processing the document. Please try again."
                            st.session_state.messages.append(AIMessage(content=error_message))
                            st.write_stream(re.findall(r'\S+|\s+', error_message))
                    else:
                        logger.info("Processing Text Query")
                        try:
                            # Process the user input
                            inputs = {
                                "messages": [HumanMessage(prompt)],
                                "user_level": user_level
                            }
                            
                            # Simulate failures if test mode is active
                            if "test_failure" in st.session_state:
                                failure_type = st.session_state["test_failure"]
                                if failure_type == "timeout":
                                    raise TimeoutError("Simulated LLM timeout")
                                elif failure_type == "error_response":
                                    raise Exception("Simulated LLM error response")
                                elif failure_type == "json_parse":
                                    # Return malformed JSON to trigger parse error
                                    return {"messages": [AIMessage(content="{malformed json}")]}
                            
                            current_graph = text_workflow.compile(memory)
                            output = current_graph.invoke(inputs, langgraph_config)
                            response = output["messages"][-1].content
                            
                            # Now that we have a successful response, save both messages
                            db.save_message(user_id, chat_id, "user", prompt)
                            db.save_message(user_id, chat_id, "assistant", response)
                            
                            st.session_state.messages.append(AIMessage(content=response))
                            
                            stream_message = re.findall(r'\S+|\s+', response)
                            full_response = st.write_stream(stream_message)

                            # Clear test failure state after successful test
                            if "test_failure" in st.session_state:
                                st.session_state.pop("test_failure")
                                st.success("Test completed successfully")
                                
                        except Exception as e:
                            logger.error(f"Error processing text query: {str(e)}")
                            error_message = "I apologize, but I encountered an error processing your question. Please try again."
                            st.session_state.messages.append(AIMessage(content=error_message))
                            st.write_stream(re.findall(r'\S+|\s+', error_message))
                            
                            # Clear test failure state after failed test
                            if "test_failure" in st.session_state:
                                st.session_state.pop("test_failure")
                                st.success("Test completed successfully")
            
                        
    
        # After processing the user input and getting a response
        # Check if we should run level analysis
        if should_analyze_user_level(user_id) and st.session_state["user_level"] not in ["", "null", None]:
            analyse_user_progress(user_id, llm_chat_history, user_level, langgraph_config)

def learning_page():
    """Render the combined topics and recommendations page."""
    st.title("📚 Your Learning Journey")
    
    # Ensure the user is logged in and has a user_id in session state
    if st.session_state["authentication_status"] in [None, False]:
        st.error("User not logged in. Please log in to view your learning journey.")
        st.stop()

    user_id = st.session_state["user_id"]
    user_level = st.session_state.get("user_level", "beginner")
    
    # Display user level with enhanced styling
    st.markdown(f"""
    <div style="margin-bottom: 1.5rem;">
        <span style="font-weight: 500;">Your current level:</span> 
        <span style="background-color: #8c52ff; padding: 3px 10px; border-radius: 12px; font-weight: 600;">{user_level.capitalize()}</span>
    </div>
    """, unsafe_allow_html=True)
    
    # Create tabs for different views
    tab1, tab2 = st.tabs(["Topics Learned", "Recommended Topics"])
    
    with tab1:
        # Add search functionality
        search_query = st.text_input("🔍 Search topics", placeholder="Type to search...")
        
        # Retrieve topics from the database
        topics = db.get_user_topics(user_id)
        
        if topics != "{}":
            topics = json.loads(topics)
            
            # Filter topics based on search query
            filtered_topics = {}
            for parent, subtopics in topics.items():
                if search_query.lower() in parent.lower() or any(search_query.lower() in sub.lower() for sub in subtopics):
                    filtered_topics[parent] = subtopics
            
            # Display total topics count
            # total_topics = sum(len(subtopics) for subtopics in filtered_topics.values())
            parent_topics = len(filtered_topics)
            st.sidebar.metric("Total Topics Learned", parent_topics)
            
            # Display topics in a grid layout
            cols = st.columns(2)
            for i, (parent, subtopics) in enumerate(filtered_topics.items()):
                with cols[i % 2]:
                    # Create an expandable card for each topic
                    with st.expander(f"{parent.replace('_', ' ').title()}", expanded=False):
                        # Topic header with subtopic count
                        st.markdown(
                            f"""
                            <div style="margin-bottom: 10px;">
                                <span style="color: #666; font-size: 0.9em;">
                                    {len(subtopics)} subtopic{'s' if len(subtopics) != 1 else ''}
                                </span>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        
                        # Display subtopics in a clean list
                        for subtopic in subtopics:
                            st.markdown(f"- {subtopic.replace('_', ' ').title()}")
        else:
            st.info("You haven't learned any topics yet. Start interacting with the chatbot to build your learning history!")
    
    with tab2:
        # Optional controls for recommendation settings
        with st.expander("Recommendation Settings", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                num_recommendations = st.slider(
                    "Number of recommendations", 
                    min_value=1, 
                    max_value=5, 
                    value=2,
                    help="Choose how many topic recommendations to display"
                )
            with col2:
                difficulty_filter = st.selectbox(
                    "Filter by difficulty",
                    ["All", "Beginner", "Intermediate", "Advanced"],
                    help="Filter recommendations by difficulty level"
                )
        
        topics_str = db.get_user_topics(user_id)
        
        # Convert string representation to dictionary
        try:
            if isinstance(topics_str, str):
                topics = json.loads(topics_str) if topics_str and topics_str != "{}" else {}
            else:
                topics = topics_str or {}
        except json.JSONDecodeError:
            st.warning("Error loading your topic history. Showing general recommendations instead.")
            topics = {}
        
        # Get and display recommendations
        saved_data = db.get_topic_recommendations_from_db(user_id)
        saved_recommendations = saved_data.get("recommendations", [])
        saved_timestamp = saved_data.get("timestamp")
        
        # Determine if recommendations are stale
        recommendations_stale = False
        if saved_timestamp:
            try:
                import datetime
                if isinstance(saved_timestamp, str):
                    timestamp_dt = datetime.datetime.strptime(saved_timestamp, "%Y-%m-%d %H:%M:%S")
                    timestamp_dt = timestamp_dt.replace(tzinfo=datetime.timezone.utc)
                    now_utc = datetime.datetime.now(datetime.timezone.utc)
                    time_diff = now_utc - timestamp_dt
                    recommendations_stale = time_diff.total_seconds() > 432,000  # 5 days
                else:
                    recommendations_stale = (time.time() - saved_timestamp) > 432,000
            except (ValueError, TypeError) as e:
                print(f"Error parsing timestamp: {e}")
                recommendations_stale = True
        else:
            recommendations_stale = True
        
        if saved_recommendations and len(saved_recommendations) != num_recommendations:
            recommendations_stale = True
        
        # Use saved recommendations if available and not stale
        if saved_recommendations and not recommendations_stale:
            recommendations = saved_recommendations
            
            # Show info about when these were generated
            if isinstance(saved_timestamp, str):
                try:
                    timestamp_dt = datetime.datetime.strptime(saved_timestamp, "%Y-%m-%d %H:%M:%S")
                    timestamp_dt = timestamp_dt.replace(tzinfo=datetime.timezone.utc)
                    now_utc = datetime.datetime.now(datetime.timezone.utc)
                    time_diff = now_utc - timestamp_dt
                    hours_ago = int(time_diff.total_seconds() / 3600)
                    
                    if hours_ago < 1:
                        time_str = "less than an hour ago"
                    elif hours_ago == 1:
                        time_str = "1 hour ago"
                    elif hours_ago < 24:
                        time_str = f"{hours_ago} hours ago"
                    else:
                        days = hours_ago // 24
                        time_str = f"{days} day{'s' if days > 1 else ''} ago"
                    
                    st.info(f"Using recommendations generated {time_str}. Click 'Refresh' for fresh suggestions.", icon="ℹ️")
                except (ValueError, TypeError) as e:
                    print(f"Error formatting timestamp: {e}")
                    st.info("Using saved recommendations. Click 'Refresh' for fresh suggestions.", icon="ℹ️")
        else:
            # Generate new recommendations
            with st.spinner("Analyzing your learning history..."):
                
                recommendations = get_topic_recommendations(
                    topics, 
                    user_level, 
                    max_recommendations=num_recommendations
                )
                
                
                # Save the new recommendations to the database
                db.save_topic_recommendations(user_id, recommendations)
                st.success("Generated fresh recommendations based on your current progress!")
        
        if st.sidebar.button("Reset Topics", type='primary', help="Clear all topics learned by the user."):
            db.update_user_topics(user_id, {})
            st.toast("All topics have been cleared.")
            st.rerun()
        
        if recommendations:
            # Add a refresh button
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown("### Your Next Learning Adventures")
            with col2:
                refresh_clicked = st.button("🔄 Refresh", key="refresh_recs")

            if refresh_clicked:
                with st.spinner("Creating fresh recommendations..."):
                    # Force new recommendations by passing empty saved recommendations
                    new_recommendations = get_topic_recommendations(
                        topics,
                        user_level,
                        max_recommendations=num_recommendations
                    )
                    if new_recommendations:
                        db.save_topic_recommendations(user_id, new_recommendations)
                        recommendations = new_recommendations  # Update the current recommendations
                        st.toast("Recommendations refreshed!", icon="✅")
                    else:
                        st.error("Failed to generate new recommendations. Please try again.")
            
            # Display recommendations in an engaging card-like format
            for i, rec in enumerate(recommendations, 1):
                topic_name = rec.get("topic", "").replace("_", " ").title()
                
                # Apply difficulty filter if selected
                if difficulty_filter != "All" and rec.get("difficulty", "").lower() != difficulty_filter.lower():
                    continue
                
                with st.container():
                    # Display the recommendation card
                    st.markdown(
                        f"""
                        <div style="padding: 20px; border: 1px solid #f0f2f6; border-radius: 10px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                                <h3 style="margin: 0;">{i}. {topic_name}</h3>
                                <span style="background-color: #8c52ff; color: white; padding: 3px 8px; border-radius: 12px; font-size: 0.8em;">
                                    {rec.get('difficulty', 'Beginner')}
                                </span>
                            </div>
                            <p style="color: #666; margin-bottom: 10px;"><i>{rec.get('description', '')}</i></p>
                            <p style="margin-bottom: 15px;"><strong>Why:</strong> {rec.get('reason', '')}</p>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
        else:
            st.warning("Unable to generate recommendations at this time. Please try again later.")
            if st.button("🔄 Try Again"):
                st.rerun()

if st.session_state["authentication_status"] in [None,False]:
    auth_page()
    
else:   
    page_names_to_funcs = {
    "Chatbot": chatbot_page,
    "Learning Journey": learning_page,
    }
    
    if "user_level" not in st.session_state:
        user_info = db.get_user_by_email(st.session_state['email'])
        if user_info:
            st.session_state["user_level"] = user_info.get("user_level", "")
        else:
            st.session_state["user_level"] = ""
    
    if st.session_state["user_level"].lower() in ["beginner", "intermediate", "advanced"]:
        page_name = st.sidebar.selectbox("Select a page", list(page_names_to_funcs.keys()))
    else:
        page_name = "Chatbot"

    # Place logout button in sidebar
    if authenticator.logout('Logout','sidebar',key='main'):
        clear_session()
        st.rerun()
    st.sidebar.divider()
    
    # Render the selected page
    page_names_to_funcs[page_name]()

        