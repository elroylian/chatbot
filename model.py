from langchain_openai import ChatOpenAI
import streamlit as st

# Initialize the LLM
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0

llm_selected = ChatOpenAI(
    model = DEFAULT_MODEL,
    api_key = st.secrets["OpenAI_key"],
    temperature = DEFAULT_TEMPERATURE
)