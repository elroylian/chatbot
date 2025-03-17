"""
Topic Recommendation Module for DSA Chatbot

This module analyzes a user's topics and level to provide tailored recommendations
for next topics to study in Data Structures and Algorithms.
"""

import logging
import json
from typing import Dict, List, Any, Optional
from langchain_core.messages import HumanMessage
from utils.model import get_llm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_topic_recommendations(
    user_topics: Dict[str, List[str]], 
    user_level: str, 
    max_recommendations: int = 3
) -> List[Dict[str, Any]]:
    """
    Generate personalized topic recommendations using LLM based on user's current level and topics.
    
    Args:
        user_topics: Dictionary of topics the user has already learned
        user_level: User's competency level (beginner, intermediate, advanced)
        max_recommendations: Maximum number of recommendations to return
        
    Returns:
        List of recommendation objects with topic name, description, and reason
    """
    try:
        # Normalize the user level to handle case variations
        user_level = user_level.lower() if user_level else "beginner"
        
        # Format user's existing topics for the prompt
        topics_str = ""
        if user_topics:
            topics_str = "Previously learned topics:\n"
            for parent_topic, subtopics in user_topics.items():
                topics_str += f"- {parent_topic}\n"
                if isinstance(subtopics, list):
                    for subtopic in subtopics:
                        topics_str += f"  - {subtopic}\n"
        else:
            topics_str = "No previous topics learned yet."
        
        # Create the prompt for the LLM
        prompt = f"""You are a Data Structures and Algorithms (DSA) learning advisor for a student at the {user_level} level.

{topics_str}

Your task is to recommend the next {max_recommendations} most appropriate DSA topics for this student to learn based on their current level and what they've already studied.

Follow these guidelines:
1. If they haven't learned any topics yet, focus on foundational topics appropriate for their level.
2. If they have learned some topics, recommend logical next steps that build on their knowledge.
3. Ensure recommendations follow a natural learning progression.
4. Consider both breadth (exploring different areas) and depth (building on existing knowledge).
5. Occasionally include challenge topics that push them slightly beyond their comfort zone.

For each recommendation, provide:
- topic: The specific DSA topic name (use snake_case)
- description: A brief, engaging explanation of what this topic is about (2-3 sentences)
- reason: Why this topic is specifically appropriate for this student right now
- value_proposition: What they'll gain by learning this topic
- fun_fact: An interesting application or insight about this topic
- difficulty: The recommended difficulty level for this topic (Beginner/Intermediate/Advanced), considering both the topic's inherent complexity and the student's current level

Respond with exactly {max_recommendations} recommendations in a valid JSON array.
Each object should have the fields described above.
Your response must be ONLY valid JSON with no introduction or explanation.
"""
        
        # Get recommendations from LLM
        llm = get_llm(temperature=0.7)  # Higher temperature for creative, varied recommendations
        response = llm.invoke([HumanMessage(content=prompt)])
        
        # Extract and parse JSON response
        recommendations = extract_json_recommendations(response.content)
        
        # Validate and format recommendations
        formatted_recommendations = []
        for rec in recommendations[:max_recommendations]:
            # Ensure all required fields are present
            formatted_rec = {
                "topic": rec.get("topic", "unknown_topic").lower().replace(" ", "_"),
                "description": rec.get("description", ""),
                "reason": rec.get("reason", ""),
                "value_proposition": rec.get("value_proposition", ""),
                "fun_fact": rec.get("fun_fact", ""),
                "difficulty": rec.get("difficulty", "Beginner")
            }
            formatted_recommendations.append(formatted_rec)
        
        logger.info(f"Generated {len(formatted_recommendations)} recommendations for {user_level} user")
        return formatted_recommendations
        
    except Exception as e:
        logger.error(f"Error generating topic recommendations: {e}")
        # Return fallback recommendations based on level
        return get_fallback_recommendations(user_level, max_recommendations)

def extract_json_recommendations(response_text: str) -> List[Dict[str, Any]]:
    """
    Extract valid JSON recommendations from the LLM response.
    
    Args:
        response_text: Raw text returned by the LLM
        
    Returns:
        List of recommendation objects
    """
    # Clean up response to extract JSON
    try:
        # First try direct JSON parsing
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass
        
        # Try with markdown code block extraction
        if "```json" in response_text:
            json_block = response_text.split("```json")[1].split("```")[0].strip()
            return json.loads(json_block)
        elif "```" in response_text:
            json_block = response_text.split("```")[1].strip()
            return json.loads(json_block)
        
        # Try to find JSON array pattern
        import re
        match = re.search(r'\[\s*\{.*\}\s*\]', response_text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
            
        # If all else fails, look for individual JSON objects and combine them
        objects = re.findall(r'\{\s*"topic".*?\}', response_text, re.DOTALL)
        if objects:
            combined = f"[{','.join(objects)}]"
            return json.loads(combined)
            
    except Exception as e:
        logger.error(f"Error extracting JSON from response: {e}")
    
    # Return empty list if all parsing attempts fail
    return []

def get_fallback_recommendations(user_level: str, max_count: int = 2) -> List[Dict[str, Any]]:
    """
    Provide fallback recommendations if LLM-based recommendations fail.
    
    Args:
        user_level: User's competency level
        max_count: Maximum number of recommendations
        
    Returns:
        List of basic recommendation objects
    """
    fallbacks = {
        "beginner": [
            {
                "topic": "arrays", 
                "description": "Fundamental data structure for storing collections of elements in contiguous memory locations.",
                "reason": "Essential foundation for all data structure learning",
                "value_proposition": "Master the building block that most other data structures build upon",
                "fun_fact": "Arrays power everything from image processing to game development",
                "difficulty": "Beginner"
            },
            {
                "topic": "linked_lists",
                "description": "Chain-like data structure where elements connect through references.",
                "reason": "Important contrast to arrays with different performance characteristics",
                "value_proposition": "Learn efficient insertion and deletion operations",
                "fun_fact": "Linked lists are used to implement file systems and music playlists",
                "difficulty": "Beginner"
            },
            {
                "topic": "binary_search",
                "description": "Efficient algorithm for finding an item in a sorted list by repeatedly dividing the search interval.",
                "reason": "Foundation for understanding algorithmic efficiency",
                "value_proposition": "Understand logarithmic time complexity and divide-and-conquer approaches",
                "fun_fact": "Binary search can find a name in a phone book of millions in just ~20 steps",
                "difficulty": "Beginner"
            }
        ],
        "intermediate": [
            {
                "topic": "binary_trees",
                "description": "Hierarchical data structure where each node has at most two children.",
                "reason": "Fundamental for understanding hierarchical data representation",
                "value_proposition": "Opens the door to efficient searching, sorting, and organizing data",
                "fun_fact": "Binary trees are used in compression algorithms like Huffman coding",
                "difficulty": "Intermediate"
            },
            {
                "topic": "hash_tables",
                "description": "Data structure that implements an associative array using a hash function.",
                "reason": "Critical for understanding efficient lookup operations",
                "value_proposition": "Achieve constant-time operations for many common tasks",
                "fun_fact": "Hash tables power dictionary implementations in most programming languages",
                "difficulty": "Intermediate"
            },
            {
                "topic": "graph_algorithms",
                "description": "Techniques for traversing, searching, and analyzing graph structures.",
                "reason": "Essential for solving complex relationship-based problems",
                "value_proposition": "Model and solve real-world network problems efficiently",
                "fun_fact": "Graph algorithms power social networks, GPS navigation, and recommendation systems",
                "difficulty": "Intermediate"
            }
        ],
        "advanced": [
            {
                "topic": "dynamic_programming",
                "description": "Method for solving complex problems by breaking them into simpler subproblems.",
                "reason": "Powerful paradigm for optimization problems",
                "value_proposition": "Efficiently solve otherwise exponential-time problems",
                "fun_fact": "Dynamic programming is used in DNA sequence alignment and resource allocation",
                "difficulty": "Advanced"
            },
            {
                "topic": "advanced_graph_algorithms",
                "description": "Sophisticated techniques for solving complex network problems like flow, matching, and shortest paths.",
                "reason": "Extended applications of graph theory to complex problems",
                "value_proposition": "Tackle industry-scale optimization challenges",
                "fun_fact": "These algorithms power airline scheduling, internet routing, and supply chain optimization",
                "difficulty": "Advanced"
            },
            {
                "topic": "computational_geometry",
                "description": "Algorithms for solving geometric problems like convex hulls, intersections, and proximity.",
                "reason": "Specialized domain with unique algorithm approaches",
                "value_proposition": "Apply DSA concepts to spatial reasoning and problems",
                "fun_fact": "Powers computer graphics, robotics, and geographic information systems",
                "difficulty": "Advanced"
            }
        ]
    }
    
    level_fallbacks = fallbacks.get(user_level.lower(), fallbacks["beginner"])
    return level_fallbacks[:max_count]

def format_recommendations_for_display(recommendations: List[Dict[str, Any]]) -> str:
    """
    Format topic recommendations for display in the UI.
    
    Args:
        recommendations: List of recommendation objects
        
    Returns:
        Formatted markdown string for display
    """
    if not recommendations:
        return "No recommendations available at this time."
    
    formatted = "## Recommended Topics for You\n\n"
    
    for i, rec in enumerate(recommendations, 1):
        topic_name = rec["topic"].replace("_", " ").title()
        formatted += f"### {i}. {topic_name}\n\n"
        
        if "description" in rec and rec["description"]:
            formatted += f"{rec['description']}\n\n"
        
        formatted += f"**Why this topic:** {rec['reason']}\n\n"
        
        if "value_proposition" in rec and rec["value_proposition"]:
            formatted += f"**Value:** {rec['value_proposition']}\n\n"
            
        if "fun_fact" in rec and rec["fun_fact"]:
            formatted += f"**Fun fact:** {rec['fun_fact']}\n\n"
        
        formatted += "---\n\n"
    
    return formatted