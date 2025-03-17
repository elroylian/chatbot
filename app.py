"""



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
from utils.level_manager import should_analyze_user_level

## TO DO
# Test promoting and demoting users
# Analysis should only be done after initial assessment
# Analysis should be done when user 'Clear History'
# Check topics page when user reloads page after closing (???)
# See if there is a way to update state in the graph


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

CHATBOT_VERSION = "2.0.1"
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

initial_graph = workflow.compile(checkpointer=memory)
document_text_graph = document_text_workflow.compile(memory)
text_graph = text_workflow.compile(memory)
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

if(cookie_session_available):
    st.session_state["authentication_status"] = True
    user_data = db.get_user_by_username(cookie_session_available["username"])
    roles = json.loads(user_data["roles"])
    st.session_state["roles"] = roles["roles"]
    st.session_state["email"] = user_data["email"]
    st.session_state["username"] = user_data["username"]

def clear_session():
    # Reset chat history when user logs out
    logger.info("Clearing session variables")
    session_vars = ["messages", "llm_chat_history", "user_level", "user_topics"]
    for var in session_vars:
        if var in st.session_state:
            del st.session_state[var]   

def reset_all_graph_states(config):
    empty_messages = []
    initial_graph.update_state(values={"messages": empty_messages}, config=config)
    document_text_graph.update_state(values={"messages": empty_messages}, config=config)
    text_graph.update_state(values={"messages": empty_messages}, config=config)

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
    st.sidebar.text(f"Version: {CHATBOT_VERSION}" )
    st.sidebar.divider()
    st.sidebar.text(f"Welcome, {st.session_state['username']}!")
    st.sidebar.write("Your account")
    
    authenticator.login('unrendered',clear_on_submit=True)
    if st.session_state.get('authentication_status'):
        authenticator.logout('Logout','sidebar',key='main',callback=clear_session())
    
    
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
                
                text_graph.update_state(values = {"messages": st.session_state["messages"]}, config = langgraph_config)
                document_text_graph.update_state(values = {"messages": st.session_state["messages"]}, config = langgraph_config)
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
    
    # Add sidebar options
    st.sidebar.write("Options")
    
    # Clear chat history
    if st.sidebar.button("Clear Chat History",type='primary'):
        # st.session_state["llm_chat_history"] = []
        st.session_state["messages"] = []
        
        # Reset all graph states
        reset_all_graph_states(langgraph_config)
        
        db.clear_chat_history(user_id, chat_id)
        st.toast("Chat history cleared successfully.",icon="✅")

    # Add file uploader to sidebar based on user assessment status
    if st.session_state["user_level"] in ["", "null", None]:
        st.sidebar.warning("Complete your initial assessment to unlock file uploads. Start by asking a question in the chat.")
    else:
        if "uploader_key" not in st.session_state:
            st.session_state["uploader_key"] = 0
        
        def update_key():
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
                    
                output = initial_graph.invoke(input_dict, langgraph_config)
                
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
                            text_graph.update_state(values = {"messages": st.session_state["messages"]}, config = langgraph_config)
                            document_text_graph.update_state(values = {"messages": st.session_state["messages"]}, config = langgraph_config)
                            initial_graph.update_state(values = {"messages": st.session_state["messages"]}, config = langgraph_config)
                            
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
            
                with st.spinner("Thinking..."):                        
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
                        logger.info("Processing Text Query")
                        
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
        if should_analyze_user_level(user_id) and st.session_state["user_level"] not in ["", "null", None]:
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
                    db.update_user_data(user_id, user_level, user_email)
                    db.update_user_topics(user_id, topics)
                    
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Error processing analysis result: {e}")

def topics():
    st.title("📚 Topics You've Learned")

    # Ensure the user is logged in and has a user_id in session state
    if st.session_state["authentication_status"] in [None,False]:
        st.error("User not logged in. Please log in to view your topics.")
        st.stop()

    user_id = st.session_state["user_id"]
    
    # Retrieve topics from the database using the get_user_topics() function
    topics = db.get_user_topics(user_id)  # Expected to return a dict {parent_topic: [subtopics]}
    topics = json.loads(topics) if topics else {}
    
    if topics != "{}":
        # Sidebar elements: filter and overview metric
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

if st.session_state["authentication_status"] in [None,False] or cookie_session_available is None:
# if st.session_state["authentication_status"] in [None,False]:
    auth_page()
    
else:
    page_names_to_funcs = {
    "Chatbot": chatbot_page,
    "Topics": topics,
    }

    page_name = st.sidebar.selectbox("Choose a page", page_names_to_funcs.keys())
    page_names_to_funcs[page_name]()

        