import streamlit as st
from st_chat_message import message
import pandas as pd
import numpy as np
from openai import OpenAI
from langchain_community.llms import Ollama
from langchain.schema import (AIMessage, HumanMessage, SystemMessage)
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from prompt_engineering import insert_input

# Example markdown in Streamlit
markdown = """
### HTML in markdown is ~quite~ **unsafe**
<blockquote>
  However, if you are in a trusted environment (you trust the markdown). You can use allow_html props to enable support for html.
</blockquote>

* Lists
* [ ] todo
* [x] done

Math:

Lift($L$) can be determined by Lift Coefficient ($C_L$) like the following
equation.

$$
L = \\frac{1}{2} \\rho v^2 S C_L
$$

~~~py
import streamlit as st

st.write("Python code block")
~~~

~~~js
console.log("Here is some JavaScript code")
~~~

"""

def on_input_change():
    user_input = st.session_state.user_input
    st.session_state.user.append(user_input)
    # response = llm.invoke(user_input)
    # response = chain.invoke(user_input)
    response = insert_input(user_input)
    st.session_state.generated.append(response)

def on_btn_click():
    del st.session_state.user[:]
    del st.session_state.generated[:]
    
st.session_state.setdefault(
    'user', 
    []
)
st.session_state.setdefault(
    'generated', 
    []
)

# Initialize the model with the base_url where it is running
llm = Ollama(model="gemma2:2b", base_url="http://localhost:11434")

# prompt_template = """
# You are a Data Structures and Algorithms Expert specializing in explaining complex concepts in a simple, structured manner. 

# Based on the concept of {concept}, provide a clear and detailed explanation in bullet points, including examples where appropriate, and summarize key takeaways.

# If the input is unclear, ask for clarification, until you are 95%\ certain. For example: "Could you please provide more details about the concept you'd like me to explain?"
# """
# prompt = PromptTemplate(
#     input_variables=['concept'],
#     template=prompt_template
# )

# chain = prompt | llm | StrOutputParser()
# response = llm.invoke(prompt.format(concept="Insertion Sort"))
# print(response)

# print(chain.invoke("Insertion Sort"))

# Set up Streamlit interface
st.title("Chat with LLM")

chat_placeholder = st.empty()

# Create a container for the chat UI
with chat_placeholder.container():
    for i in range(len(st.session_state['generated'])):                
        message(st.session_state['user'][i], is_user=True, key=f"{i}_user")
        message(
            # st.session_state['generated'][i]['data'], 
            # key=f"{i}", 
            # allow_html=True,
            # is_table=True if st.session_state['generated'][i]['type']=='table' else False
            st.session_state['generated'][i],
            key=f"{i}",
            # allow_html=True
        )
    
    st.button("Clear message", on_click=on_btn_click)

with st.container():
    st.text_input("User Input:", on_change=on_input_change, key="user_input")
            
