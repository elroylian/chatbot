"""
User Level Assessment Module for DSA Chatbot

This module analyzes conversations to determine appropriate user competency levels
in Data Structures and Algorithms, tracking topics covered and providing level recommendations.
"""

import logging
from typing import Annotated, Sequence, Dict, Any, List
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from langgraph.graph import END, StateGraph, START
import streamlit as st
import json
from utils.model import get_llm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
CONFIDENCE_THRESHOLD = 0.8

class AgentState(TypedDict):
    """State management for level assessment"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_level: str
    previous_topics: Dict[str, List[str]] = {}

# Keep this model for compatibility, but we'll use a simpler approach
class LevelAssessment(BaseModel):
    current_level: str = Field(description="User's current level")
    recommendation: str = Field(description="Promote/Maintain/Demote")
    confidence: float = Field(description="Confidence score 0-1")
    evidence: List[str] = Field(description="Supporting evidence from questions")
    reasoning: List[str] = Field(description="Reasons for recommendation")
    topics: Dict[str, List[str]] = Field(description="Hierarchical topics; keys are parent topics and values are lists of subtopics")

def format_conversation_context(messages: List[BaseMessage]) -> str:
    """Format conversation context from messages"""
    return "\n".join([
        f"{'User: ' if isinstance(m, HumanMessage) else 'Assistant: '}{m.content}"
        for m in messages
    ])

def analyze_user_level(state: AgentState) -> Dict[str, Any]:
    """
    Analyze conversation to assess user's DSA level and extract topics covered.
    
    Args:
        state: Current state containing messages, user level, and previously covered topics
        
    Returns:
        Updated state with assessment results
    """
    logger.info("Analyzing user level and topics")
    
    messages = state["messages"]
    user_level = state["user_level"]
    previous_topics = state.get("previous_topics", {})
    
    # Format conversation context for prompt
    conversation_context = format_conversation_context(messages)
    
    # Create a simple direct prompt for assessment
    assessment_prompt = f"""Assess the user's learning progression in Data Structures and Algorithms (DSA) based solely on the following conversation and previously covered topics. Do not infer or add topics that were not explicitly mentioned in this conversation or in the previous analysis.

Current Level: {user_level}

Previously Covered Topics:
{json.dumps(previous_topics, indent=2)}

Level Definitions:
- Beginner: Focuses on fundamental concepts (e.g., simple definitions of basic algorithms or data structures).
- Intermediate: Explores more detailed aspects or multiple related topics.
- Advanced: Asks in-depth, technical questions about optimization, complex algorithms, or system-level design.

<INTERACTION>
{conversation_context}
</INTERACTION>

<EVALUATION_PROCESS>
Please think through this step by step:

STEP 1: Analyze the content
- Review the entire conversation carefully
- Identify specific DSA concepts mentioned
- Note the depth and complexity of questions and explanations

STEP 2: Extract topics and categorize
- List all DSA topics explicitly mentioned
- Organize them hierarchically (parent topics and subtopics)
- Compare with previously covered topics to identify new areas

STEP 3: Assess conceptual depth
- Evaluate the technical sophistication of the questions
- Look for evidence of understanding vs. basic information seeking
- Consider whether the user is exploring advanced aspects of topics

STEP 4: Analyze progression
- Compare current engagement with their assigned level
- Look for evidence of growth or struggles
- Consider if they're ready for more advanced concepts or need reinforcement

STEP 5: Make a recommendation with confidence
- Based on your analysis, decide whether to:
  * Promote: Strong evidence they're operating above current level
  * Maintain: Appropriate engagement at current level
  * Demote: Consistent struggling with concepts at current level
- Assign a confidence score (0-1) based on clarity of evidence
</EVALUATION_PROCESS>

Create your assessment in JSON format with these fields:
- current_level: The user's current assigned level
- recommendation: Must be exactly one of: "Promote", "Maintain", or "Demote"
- confidence: A number between 0.0 and 1.0 indicating your confidence
- evidence: An array of quoted excerpts from the conversation supporting your assessment
- reasoning: An array of reasons explaining your recommendation
- topics: A nested object where keys are parent topics and values are arrays of subtopics

Your response should be ONLY the valid JSON with nothing else.
"""
    
    try:
        llm = get_llm()
        response = llm.invoke([HumanMessage(content=assessment_prompt)])
        
        # Extract JSON from the response
        content = response.content.strip()
        
        # Handle potential formatting issues
        try:
            # Clean the response if needed
            if not content.startswith("{"):
                # Try to extract JSON if it's wrapped in text
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
            
            # Remove any markdown formatting
            content = content.replace('```json', '').replace('```', '')
            
            # Parse the JSON
            assessment_data = json.loads(content)
            
            # Extract key information
            current_level = assessment_data.get("current_level", user_level)
            recommendation = assessment_data.get("recommendation", "Maintain")
            confidence = float(assessment_data.get("confidence", 0.0))
            topics = assessment_data.get("topics", {})
            
            # Log the assessment
            logger.info(f"Assessment: Level={current_level}, Recommendation={recommendation}, Confidence={confidence:.2f}")
            logger.info(f"Topics identified: {topics}")
            
            # Check confidence threshold
            if confidence < CONFIDENCE_THRESHOLD:
                logger.warning(f"Low confidence in level assessment: {confidence:.2f}")
                return {
                    "messages": [
                        AIMessage(content=json.dumps({
                            "current_level": current_level,
                            "recommendation": "Maintain",  # Default to maintain on low confidence
                            "confidence": confidence,
                            "topics": topics
                        }))
                    ]
                }
            
            # Return the full assessment
            return {
                "messages": [
                    AIMessage(content=json.dumps(assessment_data))
                ]
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error parsing assessment response: {str(e)}")
            logger.debug(f"Raw content: {content}")
            
            # Return a fallback assessment on error
            return {
                "messages": [
                    AIMessage(content=json.dumps({
                        "current_level": user_level,
                        "recommendation": "Maintain",
                        "confidence": 0.0,
                        "evidence": ["Assessment error"],
                        "reasoning": ["Error in assessment process"],
                        "topics": {}
                    }))
                ]
            }
        
    except Exception as e:
        logger.error(f"Error in analyze_user_level: {str(e)}", exc_info=True)
        
        # Return error message
        return {
            "messages": [
                AIMessage(content=json.dumps({
                    "current_level": user_level,
                    "recommendation": "Maintain",
                    "confidence": 0.0,
                    "evidence": ["System error"],
                    "reasoning": ["Error during analysis"],
                    "topics": {}
                }))
            ]
        }

# Graph setup
def create_analyser_workflow():
    """Create the analyzer workflow graph"""
    logger.info("Setting up analyzer workflow graph")
    
    workflow = StateGraph(AgentState)
    workflow.add_node("analyze", analyze_user_level)
    workflow.add_edge(START, "analyze")
    workflow.add_edge("analyze", END)
    
    return workflow


analyser_workflow = create_analyser_workflow()