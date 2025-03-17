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
    assessment_prompt = f"""Assess the user's learning progression in Data Structures and Algorithms (DSA) based solely on the following conversation and previously covered topics.

Current Level: {user_level}

Previously Covered Topics:
{json.dumps(previous_topics, indent=2)}

Level Definitions:
- Beginner: Basic understanding of fundamental concepts (arrays, linked lists, basic sorting algorithms, time complexity basics)
- Intermediate: Confident with standard data structures, algorithms, and their implementations; understands tradeoffs between different approaches
- Advanced: Deep understanding of algorithm design, optimization techniques, advanced data structures, and complex problem-solving strategies

<CONVERSATION>
{conversation_context}
</CONVERSATION>

Follow this structured evaluation process:

1. Content Analysis
   - Carefully analyze the user's questions and their focus
   - Identify main DSA concepts the user is explicitly asking about or discussing
   - Note whether the user is asking about implementations or just requesting explanations

2. Topic Extraction Guidelines
   - Extract ONLY primary DSA topics the user is actively learning or inquiring about
   - DO NOT extract implementation details, tools, or supporting concepts mentioned only in explanations
   - ONLY include topics that the user has demonstrated interest in learning about
   - For example:
     * If a user asks "What's the most efficient way to implement an LRU cache?" - extract "lru_cache" as a topic
     * DO NOT extract hash maps or linked lists if they are only mentioned as implementation details
     * If hash maps are the primary focus of the user's question, THEN extract them as a topic

3. Topic Classification
   - Group extracted topics into logical parent categories
   - Normalize topic naming using snake_case (e.g., binary_search_trees)
   - Avoid duplicating concepts across different categories
   - Focus on the user's intent rather than every technical term mentioned

4. Depth Assessment
   - Evaluate the technical depth of the user's questions
   - Consider if they're asking about basic definitions or advanced implementation details
   - Look for evidence of problem-solving ability vs. simple information gathering

5. Level Alignment & Recommendation
   - Compare the user's demonstrated knowledge with their current assigned level
   - Determine if the evidence strongly supports a level change:
     * Promote: Consistently demonstrates understanding beyond current level
     * Maintain: Appropriately engaged at current level
     * Demote: Repeatedly struggles with concepts at current level
   - Assign a confidence score (0-1) based on the strength and consistency of evidence

Provide your assessment as a valid JSON object with these fields:
{{
  "current_level": string,          // User's current level (beginner, intermediate, advanced)
  "recommendation": string,         // "Promote", "Maintain", or "Demote"
  "confidence": number,             // 0.0-1.0 confidence score
  "evidence": [                     // Array of conversation excerpts supporting your assessment
    "quote1 from conversation", 
    "quote2 from conversation"
  ],
  "reasoning": [                    // Array of reasons explaining your recommendation
    "reason1 for recommendation",
    "reason2 for recommendation"
  ],
  "topics": {{                     // Hierarchical topic structure
    "parent_topic1": [              // Parent topics in snake_case
      "subtopic1",                  // Subtopics in snake_case
      "subtopic2"
    ],
    "parent_topic2": [
      "subtopic3", 
      "subtopic4"
    ]
  }}
}}

Return ONLY a valid JSON object with no additional text.
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
            "evidence": ["System error"],
            "reasoning": ["Error during analysis"],
            "topics": previous_topics or {},
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