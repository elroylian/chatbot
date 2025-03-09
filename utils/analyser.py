"""
User Level Assessment Module for DSA Chatbot

This module analyzes conversations to determine appropriate user competency levels
in Data Structures and Algorithms, tracking topics covered and providing level recommendations.
"""

import logging
import json
import re
from typing import Annotated, Sequence, Dict, Any, List
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
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

# Confidence threshold to determine whether to trust the LLM output
CONFIDENCE_THRESHOLD = 0.8

class AgentState(TypedDict):
    """State management for level assessment"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_level: str
    previous_topics: Dict[str, List[str]]  # Previously covered topics

# Model for expected output (for documentation purposes)
class LevelAssessment(BaseModel):
    current_level: str = Field(description="User's current level")
    recommendation: str = Field(description="Promote/Maintain/Demote")
    confidence: float = Field(description="Confidence score 0-1")
    evidence: List[str] = Field(description="Supporting evidence from questions")
    reasoning: List[str] = Field(description="Reasons for recommendation")
    topics: Dict[str, List[str]] = Field(description="Hierarchical topics; keys are parent topics and values are lists of subtopics")

def extract_json(response_text: str) -> Dict[str, Any]:
    """
    Extract valid JSON from the LLM response.
    
    Args:
        response_text: Raw text returned by the LLM.
    
    Returns:
        A dictionary parsed from the JSON in the response.
        
    Raises:
        ValueError: If no valid JSON is found.
    """
    # First try direct JSON parsing
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        # Clean the text and try different approaches
        pass

    # Remove markdown formatting if present
    cleaned_text = response_text.replace('```json', '').replace('```', '')
    
    # Try to find JSON object pattern using regex
    import re
    json_match = re.search(r'\{.*\}', cleaned_text, re.DOTALL)
    
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError as e:
            logger.error(f"JSON decoding error after regex extraction: {e}")
    
    # Try another approach - find the first opening brace and last closing brace
    try:
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}')
        
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            json_substring = response_text[start_idx:end_idx+1]
            return json.loads(json_substring)
    except json.JSONDecodeError:
        logger.error("JSON decoding error using brace extraction method")
    
    # If all else fails, return an empty dict
    logger.error("Failed to extract valid JSON from response")
    return {}

def format_conversation_context(messages: List[BaseMessage]) -> str:
    """
    Format conversation context from messages.
    
    Args:
        messages: A list of conversation messages.
        
    Returns:
        A formatted string representing the conversation.
    """
    return "\n".join([
        f"{'User: ' if isinstance(m, HumanMessage) else 'Assistant: '}{m.content}"
        for m in messages
    ])

def analyze_user_level(state: AgentState) -> Dict[str, Any]:
    """
    Analyze conversation to assess the user's DSA level and extract topics covered.
    
    Args:
        state: Current state containing messages, user level, and previously covered topics.
        
    Returns:
        Updated state with assessment results packaged in an AIMessage.
    """
    logger.info("Analyzing user level and topics")
    
    messages = state["messages"]
    user_level = state["user_level"]
    previous_topics = state.get("previous_topics", {})
    
    # Format the conversation context to include in the prompt
    conversation_context = format_conversation_context(messages)
    
    # Construct the assessment prompt with detailed evaluation steps
    assessment_prompt = f"""Assess the user's learning progression in Data Structures and Algorithms (DSA) based solely on the following conversation and previously covered topics. Do not infer or add topics that were not explicitly mentioned.

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

STEP 6: Recommend next topics
- Based on their current level and previously covered topics
- Suggest 3 logical next topics they should learn
- For each recommendation, include a brief reason why it's appropriate
</EVALUATION_PROCESS>

Create your assessment in JSON format with these fields:
- current_level: The user's current assigned level
- recommendation: Must be exactly one of: "Promote", "Maintain", or "Demote"
- confidence: A number between 0.0 and 1.0 indicating your confidence
- topics: A nested object where keys are parent topics and values are arrays of subtopics
- recommended_topics: An array of 3 objects, each containing:
  * topic: The name of the recommended topic (use snake_case)
  * reason: A brief explanation of why this topic is appropriate next
  * description: A short, engaging description of what this topic is about

Your response should be ONLY the valid JSON with nothing else.
"""
    
    # Update this section in analyze_user_level function in analyser.py

    try:
        llm = get_llm()
        response = llm.invoke([HumanMessage(content=assessment_prompt)])
        raw_content = response.content.strip()
        
        # Attempt to extract and parse JSON from the response
        try:
            assessment_data = extract_json(raw_content)
            
            if not assessment_data:
                # If extraction failed, create a fallback assessment
                logger.warning("JSON extraction failed, using fallback assessment")
                assessment_data = {
                    "current_level": user_level,
                    "recommendation": "Maintain",
                    "confidence": 0.5,
                    # "evidence": ["Assessment data extraction failed"],
                    # "reasoning": ["Unable to parse LLM response"],
                    "topics": previous_topics,
                    "recommended_topics": []
                }
            
            current_level = assessment_data.get("current_level", user_level)
            recommendation = assessment_data.get("recommendation", "Maintain")
            confidence = float(assessment_data.get("confidence", 0.0))
            topics = assessment_data.get("topics", {})

            logger.info(f"Assessment: Level={current_level}, Recommendation={recommendation}, Confidence={confidence:.2f}")
            logger.info(f"Topics identified: {topics}")

            # If the confidence is below the threshold, default to maintaining the current level
            if confidence < CONFIDENCE_THRESHOLD:
                logger.warning(f"Low confidence in level assessment: {confidence:.2f}")
                assessment_data["recommendation"] = "Maintain"
                
            # Ensure we have the recommended_topics field
            if "recommended_topics" not in assessment_data:
                assessment_data["recommended_topics"] = []
            
            return {
                "messages": [AIMessage(content=json.dumps(assessment_data))]
            }
            
        except Exception as parse_error:
            logger.error(f"Error in assessment processing: {parse_error}", exc_info=True)
            fallback_data = {
                "current_level": user_level,
                "recommendation": "Maintain",
                "confidence": 0.0,
                # "evidence": ["Assessment error"],
                # "reasoning": ["Error in assessment process"],
                "topics": previous_topics or {},
                "recommended_topics": []
            }
            return {
                "messages": [AIMessage(content=json.dumps(fallback_data))]
            }
        
    except Exception as e:
        logger.error(f"Error in analyze_user_level: {str(e)}", exc_info=True)
        fallback_data = {
            "current_level": user_level,
            "recommendation": "Maintain",
            "confidence": 0.0,
            # "evidence": ["System error"],
            # "reasoning": ["Error during analysis"],
            "topics": previous_topics or {},
            "recommended_topics": []
        }
        return {
            "messages": [AIMessage(content=json.dumps(fallback_data))]
        }

def create_analyser_workflow() -> StateGraph:
    """Create the analyzer workflow graph."""
    logger.info("Setting up analyzer workflow graph")
    workflow = StateGraph(AgentState)
    workflow.add_node("analyze", analyze_user_level)
    workflow.add_edge(START, "analyze")
    workflow.add_edge("analyze", END)
    return workflow

analyser_workflow = create_analyser_workflow()

"""
- evidence: An array of quoted excerpts from the conversation supporting your assessment
- reasoning: An array of reasons explaining your recommendation
"""