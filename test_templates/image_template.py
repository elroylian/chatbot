from typing import Annotated, Literal, Sequence, Dict, Any
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from langgraph.graph import END, StateGraph, START
import json

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
    system_msg = f"""You are a friendly DSA tutor having a conversation with a student about the concepts shown in their image.
    User Level: {user_level}
    
    Structure your response with these sections, using a friendly tone throughout:

    1. Start with a warm, conversational greeting that acknowledges what you see in the image
    
    2. Use these section headers and content guidelines:
    
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
    
    3. End with an encouraging note and invitation for questions
    
    Remember to:
    - Maintain section headers for clarity while keeping content conversational
    - Balance structure with friendly, engaging explanations
    - Use subheadings to organize detailed explanations
    - Keep the overall tone warm and encouraging
    """
    
    try:
        # Initialize model
        model = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)
        
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
        
        # System message for validation
        system_msg = """Analyze the provided image for DSA (Data Structures & Algorithms) content.
        Look for:
        - Data structure visualizations (arrays, trees, graphs, etc.)
        - Algorithm flowcharts or diagrams
        - Code snippets showing DSA implementations
        - Step-by-step algorithm demonstrations
        
        Return a JSON object without any markdown formatting or code blocks, using this exact format:
        {
            "contains_dsa_content": true/false,
            "identified_concepts": ["concept1", "concept2"],
            "confidence_score": 0.0-1.0
        }
        """
        
        # Create full message list with system prompt
        full_messages = [
            HumanMessage(content=system_msg),
            latest_message  # The message containing image and user query
        ]
        
        # Get response
        validation_response = model.invoke(full_messages)
        
        try:
            # Extract JSON from potential markdown code blocks
            content = validation_response.content
            if "```json" in content:
                # Extract content between ```json and ```
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                # Extract content between ``` and ```
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                # Assume the content is raw JSON
                json_str = content
                
            # Parse the cleaned JSON string
            result = ImageAnalysisResult.parse_raw(json_str)
            
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
            
        except json.JSONDecodeError:
            print("Error parsing validation response")
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