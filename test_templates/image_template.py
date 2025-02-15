from typing import Annotated, Literal, Sequence, Dict, Any
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from langgraph.graph import END, StateGraph, START
import json
import streamlit as st

class AgentState(TypedDict):
    """State management for the image processing workflow"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_level: str
    
class ImageAnalysisResult(BaseModel):
    """Structured output for image analysis"""
    contains_dsa_content: bool = Field(description="Whether the image contains DSA-related content")
    identified_concepts: list = Field(description="List of DSA concepts identified in the image")
    confidence_score: float = Field(description="Confidence score for DSA content identification (0-1)")

def generate_dsa_response(state: AgentState) -> Dict[str, Any]:
    """Generate a conversational response about the DSA concepts in the image"""
    messages = state["messages"]
    user_level = state["user_level"]
    
    # Friendly, conversational system message
    system_msg = f"""You are a friendly DSA tutor, explain the concepts shown in the image based on the user level.
    User Level: {user_level}
    
    Structure your response with these sections, using a friendly tone throughout:
    
    1. Use these section headers and content guidelines:
    
       **What We're Looking At**
       - Friendly overview of the DSA concepts in the image
       - Use phrases like "I see you're working with..." or "This looks like..."
    
       **Key Concepts**
       - Break down the main ideas in a conversational way
       - Use clear subheadings for each concept
       - Add engaging phrases like "You know what's cool about this?"
    
       **Understanding the Details**
       - Walk through important elements with clear subheadings
       - Use relatable examples and metaphors
       - Keep technical explanations friendly and level-appropriate
    
       **Real-World Connection**
       - Share interesting applications
       - Make relatable connections to everyday experiences
    
    2. End with an encouraging note and invitation for questions
    
    Remember to:
    - Maintain section headers for clarity while keeping content conversational
    - Balance structure with friendly, engaging explanations
    - Use subheadings to organize detailed explanations
    """
    
    try:
        # Initialize model
        model = ChatOpenAI(
            model_name="gpt-4o-mini",
            temperature=0,
            streaming=True,
            api_key=st.secrets["OpenAI_key"]
        )
        
        # Create full message list with system prompt
        full_messages = [
            HumanMessage(content=system_msg),
            messages[-1]  # The message containing image and user query
        ]
        
        # Get response
        response = model.invoke(full_messages)
        
        return {
            "messages": [AIMessage(content=response.content)],
            "user_level": user_level
        }
        
    except Exception as e:
        print(f"Error generating response: {str(e)}")
        return {
            "messages": [AIMessage(content="I had a bit of trouble understanding the image. Could you tell me more about what you'd like to learn?")],
            "user_level": user_level
        }

def validate_image_content(state: AgentState) -> Dict[str, Any]:
    """Validate if the image contains DSA-related content"""
    messages = state["messages"]
    latest_message = messages[-1]
    user_level = state["user_level"]
    
    try:
        # Initialize model for image analysis
        model = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)
        
        # System message for validation with stronger formatting requirements
        system_msg = """You are an image analyzer for DSA (Data Structures & Algorithms) content.
        
        Analyze the provided image for:
        - Data structure visualizations (arrays, trees, graphs, etc.)
        - Algorithm flowcharts or diagrams
        - Code snippets showing DSA implementations
        - Step-by-step algorithm demonstrations
        
        You MUST respond with ONLY a JSON object in EXACTLY this format, with no additional text or explanation:
        {
            "contains_dsa_content": true/false,
            "identified_concepts": ["concept1", "concept2"],
            "confidence_score": 0.0
        }
        
        Rules for the response:
        1. ONLY return the JSON object, no other text
        2. No markdown formatting
        3. No code blocks
        4. No explanations before or after
        5. Use double quotes for strings
        6. confidence_score must be a number between 0 and 1
        7. identified_concepts must be a list of strings, even if empty
        """
        
        # Create full message list with system prompt
        full_messages = [
            HumanMessage(content=system_msg),
            latest_message  # The message containing image and user query
        ]
        
        # Get response
        validation_response = model.invoke(full_messages)
        content = validation_response.content.strip()
        
        # Additional cleaning to handle potential formatting issues
        try:
            # First try direct JSON parsing
            if not content.startswith("{"):
                # If response includes other text, try to extract JSON
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
            
            # Remove any markdown formatting
            content = content.replace('```json', '').replace('```', '')
            
            # Parse the cleaned JSON string
            parsed_data = json.loads(content)
            
            # Ensure the parsed data has all required fields with correct types
            validated_data = {
                "contains_dsa_content": bool(parsed_data.get("contains_dsa_content", False)),
                "identified_concepts": list(parsed_data.get("identified_concepts", [])),
                "confidence_score": float(parsed_data.get("confidence_score", 0.0))
            }
            
            # Create ImageAnalysisResult from validated data
            result = ImageAnalysisResult(**validated_data)
            
            if not result.contains_dsa_content:
                return {
                    "messages": [*messages, AIMessage(content="I don't see any specific DSA concepts in this image. Would you like to discuss a particular DSA topic instead?")],
                    "user_level": user_level,
                    "next": "end"
                }
            
            if result.confidence_score < 0.5:
                return {
                    "messages": [*messages, AIMessage(content="I think I see some DSA concepts here, but I'm not entirely sure. Could you point out what specific part you'd like to discuss?")],
                    "user_level": user_level,
                    "next": "clarify"
                }
                
            return {
                "messages": messages,
                "user_level": user_level,
                "next": "generate",
                "identified_concepts": result.identified_concepts
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing validation response: {str(e)}")
            print(f"Raw content: {content}")
            # If we can't parse the response, default to generating a response
            return {
                "messages": messages,
                "user_level": user_level,
                "next": "generate"
            }
            
    except Exception as e:
        print(f"Error in image validation: {str(e)}")
        return {
            "messages": [*messages, AIMessage(content="I had a bit of trouble with that image. Could you try uploading it again or describing what you'd like to learn about?")],
            "user_level": user_level,
            "next": "end"
        }

def clarify_request(state: AgentState) -> Dict[str, Any]:
    """Handle cases where image content needs clarification"""
    messages = state["messages"]
    user_level = state["user_level"]
    
    try:
        model = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)
        
        clarification_prompt = """Using a friendly, conversational tone:
        1. Acknowledge what you can see in the image
        2. Express what's unclear or needs more detail
        3. Ask specific questions to better understand what they want to learn
        4. Suggest possible DSA topics that might be relevant
        
        Make it feel like a natural conversation!
        """
        
        # Create full message list with system prompt
        full_messages = [
            HumanMessage(content=clarification_prompt),
            messages[-1]  # The message containing image and user query
        ]
        
        # Get response
        response = model.invoke(full_messages)
        
        return {
            "messages": [AIMessage(content=response.content)],
            "user_level": user_level
        }
        
    except Exception as e:
        print(f"Error in clarification: {str(e)}")
        return {
            "messages": [AIMessage(content="I'm not quite sure what aspect you'd like to focus on. Could you tell me more about what interests you here?")],
            "user_level": user_level
        }

# Define workflow
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("validate", validate_image_content)
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

# Compile
from test_templates.memory import memory
graph = workflow.compile(memory)

def get_image_chain(llm):
    """Create a simple message passing chain for image analysis"""
    def process_image_query(input_dict):
        system_msg = """You are a friendly DSA tutor having a casual conversation about the concepts in the image.
        User Level: {user_level}
        
        Keep your response:
        - Warm and welcoming
        - Technically accurate but conversational
        - Focused on what's interesting about the concepts
        - Engaging and encouraging
        
        End with a friendly invitation to discuss more!
        """.format(user_level=input_dict["user_level"])
        
        full_messages = [
            HumanMessage(content=system_msg),
            input_dict["messages"][-1]  # The message containing image and user query
        ]
        
        response = llm.invoke(full_messages)
        return response.content
    
    return process_image_query