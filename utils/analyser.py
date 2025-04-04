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
    assessment_prompt = f"""You are an **Data Structures and Algorithms (DSA) proficiency evaluator**. Your task is to analyze the user's learning progression based solely on their conversation history and previously covered topics.  

Assess the user's level **without making assumptions** beyond the provided data.

Current Level: {user_level}

Previously Covered Topics:
{json.dumps(previous_topics, indent=2)}

Level Definitions:
- Beginner: Basic understanding of fundamental concepts (arrays, linked lists, basic sorting algorithms, time complexity basics).
- Intermediate: Confident with standard data structures, algorithms, and their implementations; understands trade-offs between different approaches.
- Advanced: Deep understanding of algorithm design, optimization techniques, advanced data structures, and complex problem-solving strategies.

<CONVERSATION>
{conversation_context}
</CONVERSATION>

<EVALUATION_PROCESS>
Please follow these steps carefully:

STEP 1: Analyze the content  
- Review the entire conversation carefully.  
- Identify specific DSA concepts mentioned.  
- Note the depth and complexity of questions and explanations.  

STEP 2: Extract topics and categorize  
- List all DSA topics explicitly mentioned.  
- Organize them hierarchically (parent topics and subtopics).  
- Follow these topic normalization rules:  
  * Combine similar concepts under a single parent topic.  
  * If a concept appears both as a parent and subtopic, make it a parent.  
  * For similar topics (e.g., "Hash Tables: Chaining" and "Collisions: Chaining in Hash Tables"),  
    combine them under the most appropriate parent category.  
  * Use the most specific/accurate name for the topic.  
  * Avoid creating separate entries for the same concept described differently.  
- Compare with previously covered topics to identify new areas.  

STEP 3: Assess conceptual depth  
- Evaluate the technical sophistication of the questions.  
- Look for **evidence of deep understanding**, such as:  
  * Correctly applying knowledge to new problems.  
  * Comparing different approaches.  
  * Discussing trade-offs beyond surface-level explanations.  
- Ensure that struggling with a **single** advanced topic does **not** lower their level.  

STEP 4: Engagement Consideration (Optional)  
- If the user has shown **consistent lack of engagement**, mention it but do not penalize them.  
- Engagement should not be a strict factor unless it's drastically low over multiple assessments.  

STEP 5: Determine level progression  
- Promotion Criteria:  
  * User has **demonstrated understanding** of **at least 2+ topics** beyond their current level.  
  * They explore nuances and trade-offs rather than asking surface-level questions.  

- Demotion Criteria:  
  * User struggles significantly with multiple topics **at or below** their current level.  
  * They repeatedly fail to apply core concepts despite clarification.  

- If there is **too little evidence** to make a decision, maintain their current level.  

STEP 6: Make a recommendation with confidence  
- Assign **one** of the following:  
  * `"Promote"` – Evidence suggests they are operating above their current level.  
  * `"Maintain"` – Engagement and understanding align with their current level.  
  * `"Demote"` – Consistent struggles indicate they should review earlier concepts.  
- If the extracted topics are **too few**, **always** maintain the current level.  

</EVALUATION_PROCESS>

Create your assessment in JSON format with these fields:  

- `current_level`: The user's current assigned level.  
- `recommendation`: Must be exactly one of `"Promote"`, `"Maintain"`, or `"Demote"`.  
- `confidence`: A number between `0.0` and `1.0` indicating your confidence.  
- `evidence`: An **array of quoted excerpts** from the conversation supporting your assessment. If no clear evidence, set `null`.  
- `reasoning`: An **array of reasons** explaining your recommendation. If insufficient data, set `null`.  
- `topics`: A **nested object** where:  
  * Keys are **parent topics** using snake_case (e.g., `"hash_tables"`, `"sorting_algorithms"`).  
  * Values are arrays of subtopics, also in snake_case.  
  * Similar concepts should be merged under the most appropriate parent.  
  * Each concept should appear in only one place in the hierarchy.  
  * If a concept could be both a parent and subtopic, make it a parent.  
  * Follow these naming conventions:  
    - Use **descriptive but concise names** (e.g., `"binary_search_trees"` instead of `"bst"`).  
    - Keep consistent terminology (e.g., **always** use `"algorithms"`, not `"algs"`).  
    - Include the type in the name when relevant (e.g., `"search_algorithms"`, `"tree_structures"`).  
  * Example:  
    ```json
    {{
      "hash_tables": ["open_addressing", "chaining", "collision_resolution"],
      "sorting_algorithms": ["quicksort", "mergesort", "insertion_sort"]
    }}
    ```
- If there is **too little data to justify a change**, set `"recommendation": "Maintain"` and use `null` for evidence and reasoning.  

Your response should be **ONLY the valid JSON** with nothing else.

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