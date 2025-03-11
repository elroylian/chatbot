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

import streamlit_authenticator as stauth
from streamlit_authenticator.utilities import (LoginError, RegisterError,)
from utils.db_connection import ChatDatabase
from langchain_core.messages import HumanMessage
from utils.level_manager import should_analyze_user_level, get_next_level, get_previous_level

## TO DO
# Error Handling ensure db does not save user message if there is an error in the response
# Timestamp will be later than AIMessage if user prompt is saved later


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

CHATBOT_VERSION = "2.1.0"
DB_FILENAME = "chat.db"

st.sidebar.markdown(f"<div style='margin-bottom: 15px;'><span style='font-weight: bold;'>Version:</span> <code>{CHATBOT_VERSION}</code></div>", unsafe_allow_html=True)

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
    with st.spinner("Assessing your progress...", show_time=True):
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
                if analysis_data.get("recommendation") == "Promote" and analysis_data.get("confidence", 0) >= 0.8:
                    new_level = get_next_level(user_level)
                    db.update_user_level(user_id, new_level)
                    st.session_state["user_level"] = new_level
                    st.success(f"Congratulations! You've been promoted to {new_level} level.")
                
                elif analysis_data.get("recommendation") == "Demote" and analysis_data.get("confidence", 0) >= 0.9:
                    new_level = get_previous_level(user_level)
                    db.update_user_level(user_id, new_level)
                    st.session_state["user_level"] = new_level
                    st.info(f"Your level has been adjusted to {new_level}.")
                
                # Update the timestamp
                db.update_analysis_timestamp(user_id)
                
                # Merge and save topics (instead of just replacing)
                merged_topics = merge_topics(previous_topics, topics)
                db.update_user_topics(user_id, merged_topics)
                
                # # Store recommended topics in session state for displaying later
                # if "recommended_topics" in analysis_data and analysis_data["recommended_topics"]:
                #     st.session_state["recommended_topics"] = analysis_data["recommended_topics"]
                    
                #     # Display the recommendations in a small sidebar panel
                #     with st.sidebar.expander("Topic Recommendations", expanded=True):
                #         st.write("Based on your progress, consider exploring:")
                #         for i, rec in enumerate(analysis_data["recommended_topics"], 1):
                #             topic_name = rec.get("topic", "").replace("_", " ").title()
                #             if topic_name:
                #                 st.write(f"**{i}. {topic_name}**")
                #                 if "reason" in rec:
                #                     st.write(f"_{rec['reason']}_")
                #                 if st.button(f"Learn about {topic_name}", key=f"rec_{i}"):
                #                     st.session_state["prefill_question"] = f"Tell me about {topic_name}"
                #                     st.rerun()
                
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
    st.sidebar.text(f"Welcome, {st.session_state['username']}!")
    
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
        
        # Remember to remove this
        # if st.button("Get Message State"):
        #     messages = current_graph.get_state(langgraph_config)
        #     st.write(messages)
        
        
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
        st.sidebar.write("Options")
        # Clear chat history
        if st.sidebar.button("Clear Chat History",type='primary'):
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
            if st.button("Reset User Level", type='primary'):
                db.update_user_data(user_info["user_id"], "", st.session_state['email'])
                st.session_state["user_level"] = ""
                st.success("User level reset successfully.")

    with st.sidebar:
        tester_function()
        pass
    
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
                logger.info("Running INITIAL ASSESSMENT CHAIN\n")
                
                with st.spinner("Analysing your experience level..."):
                    input_dict = {
                        "messages": [HumanMessage(prompt)],
                    }
                
                current_graph = workflow.compile(memory)
                # current_graph.update_state(values = {"messages": st.session_state["messages"]}, config = langgraph_config)
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
                        
                        # Append and save assistant's message
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
                            st.session_state["messages"] = [AIMessage(content=full_response)]
                            
                            # Clear assessment chat
                            # current_graph.update_state(values = {"messages": st.session_state["messages"]}, config = langgraph_config)
                            
                            db.clear_chat_history(user_id, chat_id)
                            db.save_message(user_id, chat_id, "assistant", full_response)
                            
                            # Rerun the app
                            st.rerun()
                            

                    except json.JSONDecodeError:
                        logger.error("Error parsing JSON response")
                else:
                    logger.error("No JSON data found in response")
                    st.session_state.messages.append(AIMessage(content=response))
                    # Append and save assistant's message
                    db.save_message(user_id, chat_id, "assistant", response)

            else:
            
                with st.spinner("Thinking...",show_time=True):                        
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
                        current_graph = document_text_workflow.compile(memory)
                        # current_graph.update_state(values = {"messages": st.session_state["messages"]}, config = langgraph_config)
                        response = current_graph.invoke(state, langgraph_config)
                        
                        # Get the final message and handle response
                        final_message = response["messages"][-1].content
                        stream_message = re.findall(r'\S+|\s+', final_message)
                        full_response = st.write_stream(stream_message)
                        
                        # Save to database and update histories
                        db.save_message(user_id, chat_id, "assistant", full_response)
                        st.session_state.messages.append(AIMessage(content=full_response))

                        # Clear the uploaded files after processing
                        update_key()
                        # Also clear the processed_text and processed_images
                        processed_images = []
                        processed_text = []
                        st.rerun()
                    else:
                        logger.info("Processing Text Query")
                        
                        # Process the user input

                        inputs = {
                            "messages": [HumanMessage(prompt)],
                            "user_level": user_level
                        }
                        
                        current_graph = text_workflow.compile(memory)
                        # current_graph.update_state(values = {"messages": st.session_state["messages"]}, config = langgraph_config)
                        
                        output = current_graph.invoke(inputs, langgraph_config)
                        response = output["messages"][-1].content
                        
                        st.session_state.messages.append(AIMessage(content=response))
                        
                        stream_message = re.findall(r'\S+|\s+', response)
                        full_response = st.write_stream(stream_message)
                        db.save_message(user_id, chat_id, "assistant", response)
            
                        
    
        # After processing the user input and getting a response
        # Check if we should run level analysis
        if should_analyze_user_level(user_id) and st.session_state["user_level"] not in ["", "null", None]:
            analyse_user_progress(user_id, llm_chat_history, user_level, langgraph_config)

# Add this to the topics() function in streamlit_app.py

def topics():
    st.title("📚 Topics You've Learned")

    # Ensure the user is logged in and has a user_id in session state
    if st.session_state["authentication_status"] in [None,False]:
        st.error("User not logged in. Please log in to view your topics.")
        st.stop()

    user_id = st.session_state["user_id"]
    
    if st.sidebar.button("Reset Topics", type='primary', help="Clear all topics learned by the user."):
        db.update_user_topics(user_id, {})
        st.toast("All topics have been cleared.")
    
    # Retrieve topics from the database using the get_user_topics() function
    topics = db.get_user_topics(user_id)  # Expected to return a dict {parent_topic: [subtopics]}
    # topics = json.loads(topics) if topics else "{}"
    
    if topics != "{}":
        # Sidebar elements: filter and overview metric
        topics = json.loads(topics)
        st.sidebar.header("Filter Topics")
        parent_topics = list(topics.keys())
        selected_topic = st.sidebar.selectbox("Select a Parent Topic", parent_topics)
        
        # Display the subtopics for the selected parent topic using columns for layout
        st.header(f"Subtopics under '{selected_topic.capitalize()}'")
        subtopics = topics.get(selected_topic, [])
        if subtopics:
            col1, col2 = st.columns(2)
            for i, subtopic in enumerate(subtopics):
                if i % 2 == 0:
                    col1.write(f"- {subtopic}")
                else:
                    col2.write(f"- {subtopic}")
        else:
            st.info("No subtopics available for this topic.")
        
        # Expanders: Display all topics with their subtopics in a collapsible view
        st.write("### All Topics Overview")
        for parent, subs in topics.items():
            with st.expander(parent.capitalize(), expanded=False):
                if subs:
                    st.table([{"Subtopic": s} for s in subs])
                else:
                    st.write("No subtopics available.")
        
        # Sidebar metric: Total number of subtopics learned
        total_subtopics = sum(len(subs) for subs in topics.values())
        st.sidebar.metric("Total Subtopics Learned", total_subtopics)
        
    else:
        st.info("You haven't learned any topics yet. Start interacting with the chatbot to build your learning history!")
    
    # with tab2:
    #     st.header("Recommended Next Steps")
        
    #     # Check if we have recommendations in session state
    #     if "recommended_topics" in st.session_state and st.session_state["recommended_topics"]:
    #         recommendations = st.session_state["recommended_topics"]
            
    #         # Display recommendations in an engaging card-like format
    #         for i, rec in enumerate(recommendations, 1):
    #             topic_name = rec.get("topic", "").replace("_", " ").title()
                
    #             with st.container():
    #                 st.markdown(
    #                     f"""
    #                     <div style="padding: 15px; border: 1px solid #f0f2f6; border-radius: 10px; margin-bottom: 15px;">
    #                         <h3 style="margin-top: 0;">{i}. {topic_name}</h3>
    #                         <p><i>{rec.get('description', '')}</i></p>
    #                         <p><strong>Why:</strong> {rec.get('reason', '')}</p>
    #                     </div>
    #                     """, 
    #                     unsafe_allow_html=True
    #                 )
                    
    #                 # if st.button(f"Learn about {topic_name}", key=f"topics_rec_{i}"):
    #                 #     st.session_state["prefill_question"] = f"Tell me about {topic_name}"
    #                 #     st.session_state["current_page"] = "Chatbot"
    #                 #     st.rerun()
            
    #         # Add an option to generate new recommendations
    #         st.write("---")
    #         if st.button("Refresh Recommendations", key="refresh_topics_rec"):
    #             # This will force a new analysis next time the analyser runs
    #             st.session_state.pop("recommended_topics", None)
    #             st.toast("You'll get new recommendations after your next chat interaction.")
                
    #     else:
    #         st.info("Continue chatting with the DSA Bot to receive personalized topic recommendations based on your learning progress!")
            
    #         # Show some general recommendations based on user level
    #         user_level = st.session_state.get("user_level", "beginner")
            
    #         st.write("### While you wait, here are some general recommendations for your level:")
            
    #         general_recs = {
    #             "beginner": [
    #                 "Arrays and Basic Data Structures",
    #                 "Time Complexity Analysis",
    #                 "Basic Sorting Algorithms"
    #             ],
    #             "intermediate": [
    #                 "Binary Trees and Tree Traversal",
    #                 "Hash Tables and Their Applications",
    #                 "Graph Representations and Basic Algorithms"
    #             ],
    #             "advanced": [
    #                 "Advanced Graph Algorithms",
    #                 "Dynamic Programming Optimization",
    #                 "Advanced Data Structures (Segment Trees, Fenwick Trees)"
    #             ]
    #         }
            
    #         # Display general recommendations
    #         for rec in general_recs.get(user_level.lower(), general_recs["beginner"]):
    #             st.write(f"- {rec}")

import time
from utils.topic_recommendation import get_topic_recommendations, format_recommendations_for_display
def recommendations_page():
    """Render the topic recommendations page."""
    st.title("📚 Learning Recommendations")
    
    # Ensure the user is logged in and has a user_id in session state
    if st.session_state.get("authentication_status") in [None, False]:
        st.error("User not logged in. Please log in to view recommendations.")
        st.stop()

    user_id = st.session_state.get("user_id")
    user_level = st.session_state.get("user_level", "beginner")
    
    # Display user level with enhanced styling
    st.markdown(f"""
    <div style="margin-bottom: 1.5rem;">
        <span style="font-weight: 500;">Your current level:</span> 
        <span style="background-color: #8c52ff; padding: 3px 10px; border-radius: 12px; font-weight: 600;">{user_level.capitalize()}</span>
    </div>
    """, unsafe_allow_html=True)
    
    # Optional controls for recommendation settings
    with st.expander("Recommendation Settings", expanded=False):
        num_recommendations = st.slider(
            "Number of recommendations", 
            min_value=1, 
            max_value=5, 
            value=2,
            help="Choose how many topic recommendations to display"
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
    
    # Show topics learned so far
    if topics:
        with st.expander("Topics You've Learned", expanded=True):
            topic_count = sum(len(subtopics) for subtopics in topics.values() if isinstance(subtopics, list)) + len(topics)
            st.write(f"You've explored **{topic_count}** topics and subtopics so far!")
            
            for parent, subtopics in topics.items():
                parent_name = parent.replace("_", " ").capitalize()
                st.write(f"**{parent_name}**")
                if isinstance(subtopics, list) and subtopics:
                    st.write(", ".join([sub.replace("_", " ").capitalize() for sub in subtopics]))
    else:
        st.info("You haven't explored any topics yet. Start chatting to build your knowledge profile!")
    
    # Get and display recommendations
    # Check if we have saved recommendations in the database
    saved_data = db.get_topic_recommendations_from_db(user_id)
    saved_recommendations = saved_data.get("recommendations", [])
    saved_timestamp = saved_data.get("timestamp")
    
    # Determine if recommendations are stale
    recommendations_stale = False
    if saved_timestamp:
        # Convert SQLite timestamp string to datetime object if needed
        try:
            import datetime
            if isinstance(saved_timestamp, str):
                # Parse the database timestamp (assumed to be UTC)
                timestamp_dt = datetime.datetime.strptime(saved_timestamp, "%Y-%m-%d %H:%M:%S")
                # Make it timezone-aware by marking it as UTC
                timestamp_dt = timestamp_dt.replace(tzinfo=datetime.timezone.utc)
                
                # Get current time in UTC
                now_utc = datetime.datetime.now(datetime.timezone.utc)
                
                # Now both datetimes are UTC-aware and can be compared properly
                time_diff = now_utc - timestamp_dt
                
                # If recommendations are older than 24 hours, consider them stale
                recommendations_stale = time_diff.total_seconds() > 86400  # 24 hours
            else:
                # If timestamp is a number, compare directly (assuming it's a unix timestamp)
                recommendations_stale = (time.time() - saved_timestamp) > 86400
        except (ValueError, TypeError) as e:
            # Log the specific error for debugging
            print(f"Error parsing timestamp: {e}, value: {saved_timestamp}")
            # If timestamp can't be parsed, consider recommendations stale
            recommendations_stale = True
    else:
        # No timestamp means no recommendations, so they're stale
        recommendations_stale = True
    
    # Also check if the count of recommendations matches the requested count
    if saved_recommendations and len(saved_recommendations) != num_recommendations:
        recommendations_stale = True
    
    # Use saved recommendations if available and not stale
    if saved_recommendations and not recommendations_stale:
        recommendations = saved_recommendations
        
        # Show info about when these were generated
        if isinstance(saved_timestamp, str):
            import datetime
            try:
                # Parse the database timestamp (UTC)
                timestamp_dt = datetime.datetime.strptime(saved_timestamp, "%Y-%m-%d %H:%M:%S")
                timestamp_dt = timestamp_dt.replace(tzinfo=datetime.timezone.utc)
                
                # Get current time in UTC for comparison
                now_utc = datetime.datetime.now(datetime.timezone.utc)
                
                # Calculate time difference
                time_diff = now_utc - timestamp_dt
                hours_ago = int(time_diff.total_seconds() / 3600)
                
                # Format for display
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
    
    if recommendations:
        # Add a refresh button
        col1, col2 = st.columns([5, 1])
        with col1:
            st.markdown("### Your Next Learning Adventures")
        with col2:
            refresh_clicked = st.button("Refresh", key="refresh_recs")

        # Move the spinner outside the column structure
        if refresh_clicked:
            # Generate new recommendations
            with st.spinner("Creating fresh recommendations..."):
                new_recommendations = get_topic_recommendations(
                    topics,
                    user_level,
                    max_recommendations=num_recommendations
                )
                db.save_topic_recommendations(user_id, new_recommendations)
            st.toast("Recommendations refreshed!", icon="✅")
            st.rerun()
        
        # Display recommendations in an engaging card-like format
        for i, rec in enumerate(recommendations, 1):
            topic_name = rec.get("topic", "").replace("_", " ").title()
            
            with st.container():
                st.markdown(
                    f"""
                    <div style="padding: 15px; border: 1px solid #f0f2f6; border-radius: 10px; margin-bottom: 15px;">
                        <h3 style="margin-top: 0;">{i}. {topic_name}</h3>
                        <p><i>{rec.get('description', '')}</i></p>
                        <p><strong>Why:</strong> {rec.get('reason', '')}</p>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
                
                # Create columns for value and fun fact
                # col1, col2 = st.columns(2)
                # with col1:
                #     if "value_proposition" in rec and rec["value_proposition"]:
                #         st.markdown(f"**Value:** {rec['value_proposition']}")
                
                # with col2:
                #     if "fun_fact" in rec and rec["fun_fact"]:
                #         st.markdown(f"**Fun fact:** {rec['fun_fact']}")
                
    else:
        st.warning("Unable to generate recommendations at this time. Please try again later.")
        
        # Add a retry button
        if st.button("Try Again"):
            st.rerun()

if st.session_state["authentication_status"] in [None,False]:
    auth_page()
    
else:   
    page_names_to_funcs = {
    "Chatbot": chatbot_page,
    "Topics": topics,
    "Topic Recommendations": recommendations_page,
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
    if authenticator.logout('Logout','sidebar',key='main',callback=clear_session()):
        clear_session()
        st.rerun()
    st.sidebar.divider()
    
    # Render the selected page
    page_names_to_funcs[page_name]()

        