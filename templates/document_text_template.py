"""
Document Processing Module for DSA Chatbot

This module handles the processing of image and PDF documents,
providing specialized DSA explanations based on document content.
"""

import logging
import json
import re
from typing import Annotated, Dict, List, Literal, Sequence, Any, Optional
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from langgraph.graph import END, StateGraph, START
import streamlit as st

from utils.model import get_llm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_MODEL = "gpt-4o-mini"

class AgentState(TypedDict):
    """State management for the document processing workflow"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_level: str
    pdf_context: str = ""  # Field to store PDF context

# Keep this model for compatibility but use a simpler approach
class DocumentAnalysisResult(BaseModel):
    """Structured output for document analysis"""
    contains_dsa_content: bool = Field(description="Whether the document contains DSA-related content")
    identified_concepts: list = Field(description="List of DSA concepts identified in the document")
    confidence_score: float = Field(description="Confidence score for DSA content identification (0-1)")
    document_type: str = Field(description="Type of document: 'image', 'text', or 'both'")

def generate_dsa_response(state: AgentState) -> Dict[str, Any]:
    """
    Generate a conversational response about the DSA concepts in the document.
    
    Args:
        state: Current state containing messages, user level, and PDF context
        
    Returns:
        Updated state with generated response
    """
    logger.info("Generating DSA response for document")
    
    messages = state["messages"]
    user_level = state["user_level"]
    pdf_context = state.get("pdf_context", "")
    
    # Determine if we have PDF content
    has_pdf = pdf_context and len(pdf_context) > 0
    
    # Enhanced system message with PDF context support
    system_msg = (
    "You are a friendly DSA tutor having a conversation about the concepts shown in the document. Make complex concepts accessible and engaging as if you're chatting with a {user_level} level student.\n\n"
    
    "When explaining the document content:\n"
    "1. Start with a warm, conversational introduction about what you're seeing\n"
    "2. Break down the main concepts naturally, as if you're pointing things out to a friend\n"
    "3. Use everyday language and analogies when appropriate\n"
    "4. Express genuine interest in the interesting aspects of the concepts\n"
    "5. Connect ideas to what they might already know\n\n"
    
    "For this {user_level} level user, ensure your explanation:\n"
    "- Has the right technical depth for a {user_level}\n"
    "- Uses a warm, approachable tone throughout\n"
    "- Feels like a natural conversation, not a formal analysis\n"
    "- Connects theory to practical understanding\n\n"
    
    "Remember to explain key elements like:\n"
    "- How the data structure works or how the algorithm functions\n"
    "- Important operations and their implications\n"
    "- Time and space complexity in appropriate language\n"
    "- Any notable patterns or strategies shown in the document\n\n"
    
    "End your response with a thoughtful question or suggestion for further exploration."
)
    
    # Add PDF context if available
    if has_pdf:
        system_msg += f"\n\nPDF CONTENT:\n{pdf_context}"
        logger.info("PDF context added to system message")
    
    try:
        # Initialize model
        llm = get_llm()
        
        # Create full message list with system prompt
        full_messages = [
            HumanMessage(content=system_msg),
            messages[-1]  # The message containing image and/or text query
        ]
        
        # Get response
        response = llm.invoke(full_messages)
        logger.info("Generated response for document")
        
        return {
            "messages": [AIMessage(content=response.content)],
            "user_level": user_level,
            "pdf_context": pdf_context
        }
        
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}", exc_info=True)
        error_msg = "I had some trouble understanding the document. Could you tell me more about what you'd like to learn about the DSA concepts in it?"
        return {
            "messages": [AIMessage(content=error_msg)],
            "user_level": user_level,
            "pdf_context": pdf_context
        }

def validate_document_content(state: AgentState) -> Dict[str, Any]:
    """
    Validate if the document contains DSA-related content.
    
    Args:
        state: Current state containing messages, user level, and PDF context
        
    Returns:
        Updated state with validation result and next action
    """
    logger.info("Validating document content for DSA relevance")
    
    messages = state["messages"]
    latest_message = messages[-1]
    user_level = state["user_level"]
    pdf_context = state.get("pdf_context", "")
    
    # Determine document type
    has_image = isinstance(latest_message.content, list) and any(item.get("type") == "image_url" for item in latest_message.content)
    has_pdf = pdf_context and len(pdf_context) > 0
    document_type = "both" if (has_image and has_pdf) else ("image" if has_image else "text")
    
    logger.info(f"Document type: {document_type}")
    
    try:
        # System message for simple validation
        validation_prompt = f"""As a helpful DSA tutor, take a look at this document and determine if it contains Data Structures & Algorithms concepts.

        I'm looking for things like:
        - Visualizations or descriptions of data structures
        - Algorithm explanations or flowcharts
        - Code implementations of DSA concepts
        - Discussion of algorithmic efficiency or complexity

        Based on what you see, simply respond with one of these options:
        - "DSA_CONTENT_HIGH_CONFIDENCE" if you're confident it contains DSA material
        - "DSA_CONTENT_LOW_CONFIDENCE" if there might be some DSA content but you're not sure
        - "NO_DSA_CONTENT" if you don't see any relevant DSA content

        Just the option text is needed - no other explanation.
        """
        
        # Add PDF context to prompt if available
        if has_pdf:
            validation_prompt += f"\n\nPDF CONTENT:\n{pdf_context}"
        
        # Initialize model and get response
        llm = get_llm(temperature=0)
        validation_response = llm.invoke([
            HumanMessage(content=validation_prompt),
            latest_message  # The message containing document content
        ])
        
        result = validation_response.content.strip().upper()
        logger.info(f"Document validation result: {result}")
        
        # Process response based on content determination
        if result == "NO_DSA_CONTENT":
            logger.info("No DSA content detected in document")
            return {
                "messages": [*messages, AIMessage(content="I don't see any specific DSA concepts in this document. Would you like to discuss a particular DSA topic instead?")],
                "user_level": user_level,
                "pdf_context": pdf_context,
                "next": "end"
            }
        
        if result == "DSA_CONTENT_LOW_CONFIDENCE":
            logger.info("Low confidence in DSA content detection")
            return {
                "messages": [*messages, AIMessage(content="I think I see some DSA concepts here, but I'm not entirely sure. Could you point out what specific part you'd like to discuss?")],
                "user_level": user_level,
                "pdf_context": pdf_context,
                "next": "clarify"
            }
        
        # For high confidence or fallback to generate
        logger.info("DSA content detected with high confidence")
        return {
            "messages": messages,
            "user_level": user_level,
            "pdf_context": pdf_context,
            "next": "generate"
        }
        
    except Exception as e:
        logger.error(f"Error in document validation: {str(e)}", exc_info=True)
        # On error, provide a helpful message and end
        return {
            "messages": [*messages, AIMessage(content="I had trouble analyzing that document. Could you try describing what DSA concepts you're interested in from it?")],
            "user_level": user_level,
            "pdf_context": pdf_context,
            "next": "end"
        }

def clarify_request(state: AgentState) -> Dict[str, Any]:
    """
    Handle cases where document content needs clarification.
    
    Args:
        state: Current state containing messages, user level, and PDF context
        
    Returns:
        Updated state with clarification request
    """
    logger.info("Requesting clarification for document content")
    
    messages = state["messages"]
    user_level = state["user_level"]
    pdf_context = state.get("pdf_context", "")
    
    try:
        llm = get_llm()
        
        clarification_prompt = """Using a friendly, conversational tone:
        1. Acknowledge what you can see in the document
        2. Express what's unclear or needs more detail
        3. Ask specific questions to better understand what they want to learn
        4. Suggest possible DSA topics that might be relevant
        
        Focus equally on data structures AND algorithms in your suggestions.
        Make it feel like a natural conversation!
        """
        
        # Add PDF context if available
        if pdf_context and len(pdf_context) > 0:
            clarification_prompt += f"\n\nPDF CONTENT:\n{pdf_context}"
        
        # Create full message list with system prompt
        full_messages = [
            HumanMessage(content=clarification_prompt),
            messages[-1]  # The message containing document and user query
        ]
        
        # Get response
        response = llm.invoke(full_messages)
        logger.info("Generated clarification request")
        
        return {
            "messages": [AIMessage(content=response.content)],
            "user_level": user_level,
            "pdf_context": pdf_context
        }
        
    except Exception as e:
        logger.error(f"Error in clarification: {str(e)}", exc_info=True)
        fallback_msg = "I'm not quite sure what aspect of this document you'd like to focus on. Could you tell me more about the specific data structure or algorithm you're interested in?"
        return {
            "messages": [AIMessage(content=fallback_msg)],
            "user_level": user_level,
            "pdf_context": pdf_context
        }

# Define workflow
def create_document_text_workflow():
    """Create the document processing workflow graph"""
    logger.info("Setting up document processing workflow graph")
    
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("validate", validate_document_content)
    workflow.add_node("generate", generate_dsa_response)
    workflow.add_node("clarify", clarify_request)
    
    # Add edges with conditional routing
    workflow.add_edge(START, "validate")
    
    workflow.add_conditional_edges(
        "validate",
        lambda x: x["next"],
        {
            "generate": "generate",
            "clarify": "clarify",
            "end": END
        }
    )
    
    workflow.add_edge("generate", END)
    workflow.add_edge("clarify", END)
    
    return workflow

# Initialize workflow
document_text_workflow = create_document_text_workflow()

# def get_document_chain(llm):
#     """
#     Create a simple message passing chain for document analysis.
    
#     Args:
#         llm: Language model to use for processing
        
#     Returns:
#         Function that processes document queries
#     """
#     def process_document_query(input_dict):
#         """Process a document query using the provided LLM"""
#         user_level = input_dict["user_level"]
#         pdf_context = input_dict.get("pdf_context", "")
        
#         system_msg = f"""You are a friendly DSA tutor having a casual conversation about the concepts in the document.
#         User Level: {user_level}
        
#         Keep your response:
#         - Warm and welcoming
#         - Technically accurate but conversational
#         - Focused on what's interesting about the concepts
#         - Engaging and encouraging
#         - Balanced between data structures and algorithms
        
#         End with a friendly invitation to discuss more!
#         """
        
#         # Add PDF context if available
#         if pdf_context and len(pdf_context) > 0:
#             system_msg += f"\n\nPDF CONTENT:\n{pdf_context}"
        
#         try:
#             full_messages = [
#                 HumanMessage(content=system_msg),
#                 input_dict["messages"][-1]  # The message containing document and user query
#             ]
            
#             response = llm.invoke(full_messages)
#             return response.content
#         except Exception as e:
#             logger.error(f"Error in document chain: {str(e)}", exc_info=True)
#             return "I had some trouble analyzing that document. Could you tell me more about what you're looking for?"
    
#     return process_document_query