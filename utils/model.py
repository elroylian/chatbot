import logging
from langchain_openai import ChatOpenAI
import streamlit as st

# Constants
DEFAULT_MODEL = "gpt-4o-mini"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_api_key() -> str:
    """Safely retrieve API key from Streamlit secrets"""
    try:
        return st.secrets["OpenAI_key"]
    except KeyError:
        logger.error("OpenAI API key not found in Streamlit secrets")
        raise ValueError("OpenAI API key not found. Please set it in your Streamlit secrets.")

def get_llm(temperature: float = 0, model: str = DEFAULT_MODEL, streaming: bool = True) -> ChatOpenAI:
    """Create a ChatOpenAI instance with the given parameters"""
    return ChatOpenAI(
        model_name=model,
        temperature=temperature,
        streaming=streaming,
        api_key=get_api_key()
    )