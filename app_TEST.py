import yaml
import streamlit as st
from langchain_core.output_parsers import StrOutputParser
from yaml.loader import SafeLoader
from model import llm_selected
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from utils.chunk_doc import get_retriever
from prompt_templates.contextual_query import get_context_query_chain
from prompt_templates.qa_template import get_qa_chain
from prompt_templates.intial_template import get_initial_chain
from prompt_templates.retrieval_check import get_rc_chain
from prompt_templates.conversation_response import get_conversation_chain
from prompt_templates.image_template import get_image_chain
from utils.image_processing import process_image
from operator import itemgetter
import json
import re
import os
import streamlit_authenticator as stauth
from streamlit_authenticator.utilities import (CredentialsError,
                                               ForgotError,
                                               Hasher,
                                               LoginError,
                                               RegisterError,
                                               ResetError,
                                               UpdateError)
from utils.db_connection import ChatDatabase
from langchain_core.messages import HumanMessage
from test_templates.intial_template import app
from test_templates.retrieval_tool import graph
from test_templates.image_template import graph as image_graph

CHATBOT_VERSION = "1.4.0"
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

langgraph_config = {"configurable": {"thread_id": "abc123"}}

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

        

if st.session_state["authentication_status"] is None or st.session_state["authentication_status"] is False:
    
    clear_session()
    
    st.title('DSA Chatbot')
    
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
    # try:
    if st.session_state["authentication_status"]:
        
        # Initialize LLM chat history (for context handling)
        if "llm_chat_history" not in st.session_state:
            st.session_state["llm_chat_history"] = []

        llm_chat_history = st.session_state["llm_chat_history"]

        st.sidebar.write("Welcome, ",st.session_state['name'])
        
        if user_info := db.get_user_by_email(st.session_state['email']):
            
            # ChatID
            chat_id = user_info['user_id']+"_1"
            
            # User Info
            user_id = user_info['user_id']
            user_email = user_info['email']
            
            def tester_function():
                if "tester" in st.session_state['roles']:
                    st.title("Extra Options:")
                    st.write(db.get_user_by_email(st.session_state['email']))
                    if st.button("Reset User Level", type='primary'):
                        db.save_user_data(user_info["user_id"], "", st.session_state['email'])
                        st.session_state["user_level"] = ""
                        st.success("User level reset successfully.")
            
            with st.sidebar:
                tester_function()
            
            # Load chat history upon successful login
            user_info = db.get_user_by_email(st.session_state['email'])
            chat_id = f"{user_info['user_id']}_1"
            chat_history = db.load_chat_history(user_info['user_id'], chat_id)
            
            # If chat history exists, load it into the messages list
            if chat_history:
                st.session_state.messages = chat_history
                
                # Only load into llm_chat_history if it's empty
                if not st.session_state["llm_chat_history"]:
                    print("not IN LLM HISTORY")
                    for message in chat_history:
                        if message["role"] == "user":
                            st.session_state["llm_chat_history"].append(HumanMessage(content=message["content"]))
                        else:
                            st.session_state["llm_chat_history"].append(AIMessage(content=message["content"]))
                
                app.update_state(values = {"messages": llm_chat_history}, config = langgraph_config)
            else:
                # Initialize empty messages list
                st.session_state.messages = []
            
            # Initialize user level
            st.session_state["user_level"] = db.get_user_level(user_id)
            user_level = st.session_state["user_level"]
            
   
        else:
            st.error("User not found in the database.")
            st.stop()
            
        try:
            retriever = get_retriever()
        except Exception as e:
            st.error(f"An error occurred: {e}")
            clear_session()
            st.stop()

        contextual_query_chain = get_context_query_chain(llm)
        image_chain = get_image_chain(llm)    
        rag_chain = get_qa_chain(llm, contextual_query_chain, retriever)
        initial_chain = get_initial_chain(llm)
        retrieval_check_chain = get_rc_chain(llm)
        
        print("llm_chat_history: ", llm_chat_history)

        st.title("DSA Chatbot")
        
        # Add sidebar options
        st.sidebar.title("Options")
        authenticator.logout('Logout','sidebar')
        st.sidebar.write("Version:", CHATBOT_VERSION)
        if st.sidebar.button("Clear Chat History"):
            st.session_state["llm_chat_history"] = []
            st.session_state.messages = []
            
            # Get the current state of the app
            messages = app.get_state(langgraph_config).values["messages"]
            updated_messages = [RemoveMessage(m.id) for m in messages]
            app.update_state(values = {"messages": updated_messages}, config = langgraph_config)
            db.clear_chat_history(user_id, chat_id)

        # Add file uploader to sidebar based on user assessment status
        if st.session_state["user_level"] in ["", "null", None]:
            st.sidebar.warning("Complete your initial assessment to unlock file uploads. Start by asking a question in the chat.")
        else:
            uploaded_files = st.sidebar.file_uploader("Upload Files (Not Done)", type=["txt", "pdf", "docx", "png", "jpg", "jpeg"], accept_multiple_files=True)

            # Process the uploaded file if available
            # if uploaded_file is not None:
            #     file_details = {
            #         "filename": uploaded_file.name,
            #         "filetype": uploaded_file.type,
            #         "filesize": uploaded_file.size
            #     }
            #     st.sidebar.write("File Details:", file_details)
            uploaded_images = []
            
            if uploaded_files:
                for uploaded_file in uploaded_files:
                    if uploaded_file.size > 5 * 1024 * 1024:  # 5MB limit
                        st.sidebar.error("File too large. Please upload a file smaller than 5MB")
                    else:
                        # Handle different file types
                        if uploaded_file.type.startswith('image'):
                            try:
                                base64_image, processed_image = process_image(uploaded_file)
                                st.sidebar.image(processed_image, caption="Processed Image")
                                uploaded_images.append(base64_image)
                                
                            except Exception as e:
                                st.sidebar.error(f"Error processing image: {str(e)}")
                                
                        elif uploaded_file.type == "text/plain":
                            file_content = uploaded_file.read().decode("utf-8")
                            st.sidebar.write("File Content:", file_content)
                        
            if uploaded_images and st.sidebar.button("Clear Images"):
                uploaded_images = []
                st.sidebar.success("Images cleared")
            
            

        # Display chat messages from history on app rerun
        if "messages" in st.session_state:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        # Accept user input
        if prompt := st.chat_input("What is an Array?"):
            
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            db.save_message(user_id, chat_id, "user", prompt)
            
            # Display user message in chat message container
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Display assistant response in chat message container
            with st.chat_message("assistant"):
                
                # Initialize an empty list to hold the streamed chunks
                stream = []

                # Before processing user input, validate user level status
                if st.session_state["user_level"] in ["","null",None]:
                    
                    # New user needs assessment
                    print("RAN INITIAL CHAIN\n")
                    with st.spinner("Analysing your experience level..."):
                        input_dict = {
                            "messages": [HumanMessage(prompt)],
                        }
                        
                    output = app.invoke(input_dict, langgraph_config)
                    
                    # print("this is the output:\n",output)
                    response = output["messages"][-1].content
                    # print("this is the response:\n",response)

                    # gebgrgerg = app.get_state(config).values
                    # print(f'This is the history:\n')
                    # for message in gebgrgerg["messages"]:
                    #     message.pretty_print()
                    
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
                        db.save_message(user_id, chat_id, "assistant", response)
                        llm_chat_history.extend(
                            [
                                HumanMessage(content="Remember, you MUST generate a syntactically correct JSON object."),
                                AIMessage(content=response),
                            ]
                        )
                else:
                
                    with st.spinner("Thinking..."):
                    
                #         # Check if the user input contains an image
                        if uploaded_images:
                            print("PROCESSING IMAGE QUERY\n\n")
    
                            # Format content with image
                            content = [{"type": "text", "text": prompt}]
                            
                            # Add each image to the content
                            for img in uploaded_images:
                                content.append({
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{img}"
                                    }
                                })
                            
                            # Initialize state for image workflow
                            state = {
                                "messages": [HumanMessage(content=content)],
                                "user_level": user_level
                            }
                            
                            # Run the workflow
                            response = image_graph.invoke(state,langgraph_config)
                            
                            # Get the final message and handle response
                            final_message = response["messages"][-1].content
                            stream_message = re.findall(r'\S+|\s+', final_message)
                            full_response = st.write_stream(stream_message)
                            
                            # Save to database and update histories
                            db.save_message(user_id, chat_id, "assistant", full_response)
                            llm_chat_history.extend([
                                HumanMessage(content=prompt),
                                AIMessage(content=full_response),
                            ])
                            st.session_state.messages.append({"role": "assistant", "content": full_response})
                
                  
                        else:
                            print("PROCESSING NON-IMAGE QUERY\n")
                            
                            # Process the user input
                            from test_templates.retrieval_tool import graph
    
                            inputs = {
                                "messages": [HumanMessage(prompt)],
                                "user_level": user_level
                            }
                            output = graph.invoke(inputs, langgraph_config)
                            response = output["messages"][-1].content
                            st.session_state.messages.append({"role": "assistant", "content": response})
                            
                            state = app.get_state(langgraph_config)
                            messages = state.values["messages"]
                            print("Messages: ", messages)
                            
                            stream_message = re.findall(r'\S+|\s+', response)
                            full_response = st.write_stream(stream_message)
                            db.save_message(user_id, chat_id, "assistant", response)