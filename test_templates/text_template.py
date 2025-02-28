"""
DSA Chatbot Retrieval System

This module handles document retrieval and response generation for DSA queries.
It implements a workflow for validating input, retrieving relevant information,
and generating level-appropriate responses.
"""

import logging
from typing import Annotated, Dict, List, Literal, Sequence, Any, Optional, Tuple
from typing_extensions import TypedDict

from langchain.tools.retriever import create_retriever_tool
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, field_validator
from langgraph.prebuilt import tools_condition
from langgraph.graph.message import add_messages
from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import ToolNode

import streamlit as st
from utils.chunk_doc import get_retriever
from utils.model import get_llm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== Models and Type Definitions =====

class AgentState(TypedDict):
    """State schema for the retrieval workflow"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_level: str

# We're keeping this model to maintain backward compatibility with existing references
class ValidationResult(BaseModel):
    """Model for input validation results"""
    message_type: str = Field(
        description="Type of message: 'dsa', 'pleasantry', 'non_english', or 'other'"
    )
    response: str = Field(
        description="Response for non-DSA inputs"
    )
    
    @field_validator('message_type')
    def validate_message_type(cls, v):
        valid_types = ['dsa', 'pleasantry', 'non_english', 'other', 'english']
        if v not in valid_types:
            raise ValueError(f"message_type must be one of {valid_types}")
        return v


# Note: While we're keeping the model for compatibility, our new implementation
# avoids using structured output parsing to prevent validation errors


# We're keeping the model for backward compatibility
class ClarificationResult(BaseModel):
    """Model for question clarification results"""
    needs_clarification: bool = Field(
        description="Whether the question needs clarification",
        default=False
    )
    clarified_question: str = Field(
        description="The clarified version of the question",
        default=""
    )
    referenced_concept: str = Field(
        description="The main DSA concept referenced in the question",
        default=""
    )


class GradeResult(BaseModel):
    """Model for content grading results"""
    relevance_score: float = Field(
        description="0-1 score for topic relevance"
    )
    completeness_score: float = Field(
        description="0-1 score for answer completeness"
    )
    technical_accuracy: float = Field(
        description="0-1 score for technical accuracy"
    )
    reasoning: str = Field(
        description="Explanation for the grading decision"
    )
    
    @field_validator('relevance_score', 'completeness_score', 'technical_accuracy')
    def validate_score(cls, v):
        """Ensure scores are between 0 and 1"""
        if not 0 <= v <= 1:
            raise ValueError("Score must be between 0 and 1")
        return v


# ===== Utility Functions =====

def format_conversation_context(messages: List[BaseMessage], max_messages: int = 6) -> str:
    """Format conversation context from messages"""
    context_messages = messages[-max_messages:-1] if len(messages) > max_messages else messages[:-1]
    return "\n".join([
        f"{'User: ' if isinstance(m, HumanMessage) else 'Assistant: '}{m.content}"
        for m in context_messages
    ])


# ===== Node Functions =====

def classify_user_input(state: AgentState) -> Dict[str, Any]:
    """
    Classify user input as DSA-related, pleasantry, non-English, or other.
    
    Args:
        state: Current state containing messages and user level
        
    Returns:
        Updated state with classification result and next action
    """
    logger.info("Classifying user input")
    messages = state["messages"]
    question = messages[-1].content
    user_level = state["user_level"]
    
    try:
        # Check if current message is in English
        llm = get_llm(temperature=0.5)
        
        language_prompt = PromptTemplate(
            template="""Analyze ONLY the current input for language:

Current input: {question}

Determine if this input contains ANY non-English text or characters.
Return:
1. message_type: 'non_english' if ANY non-English content is present, 'english' if input is entirely in English
2. response: "I can only communicate in English. Please rephrase your question in English." for non-English content""",
            input_variables=["question"]
        )
        
        language_chain = language_prompt | llm.with_structured_output(ValidationResult)
        language_result = language_chain.invoke({"question": question})
        
        # Handle non-English input
        if language_result.message_type == "non_english":
            logger.info("Non-English input detected")
            return {
                "messages": [*messages, AIMessage(content="I can only communicate in English. Please rephrase your question in English.")],
                "user_level": user_level,
                "next": "redirect"
            }
        
        # Get conversation context
        conversation_context = format_conversation_context(messages)
        
        # Classify English input
        classification_prompt = PromptTemplate(
            template="""Analyze the English input as a friendly DSA tutor:

Previous conversation:
{context}

Current input: {question}

Classify the input into:

1. 'dsa' - Questions directly about:
- Data Structures (arrays, linked lists, trees, graphs, etc.)
- Algorithms (sorting, searching, traversal, etc.)
- Algorithm analysis (complexity, Big O notation)
- DSA implementation
- DSA problem-solving

2. 'pleasantry' - Friendly conversation:
- Greetings (hi, hello, hey)
- Thanks/gratitude
- Goodbyes
- Emotional responses ("that makes sense", "I'm confused")
- Small encouragements ("got it", "okay I understand")

3. 'other' - Non-DSA technical content:
- General programming
- Math questions
- Other CS topics
- Non-technical questions

For pleasantries: Respond naturally like a friendly tutor
For other: Tell user that it is out of your scope and redirect them to ask about DSA while being encouraging

Return:
1. message_type: 'dsa', 'pleasantry', or 'other'
2. response: Appropriate response for non-DSA inputs""",
            input_variables=["context", "question"]
        )
        
        chain = classification_prompt | llm.with_structured_output(ValidationResult)
        result = chain.invoke({"context": conversation_context, "question": question})
        
        if result.message_type == "dsa":
            logger.info("DSA input detected, proceeding with retrieval")
            return {
                "messages": messages, 
                "user_level": user_level, 
                "next": "proceed"
            }
        else:
            logger.info(f"Non-DSA input detected: {result.message_type}")
            return {
                "messages": [*messages, AIMessage(content=result.response)], 
                "user_level": user_level, 
                "next": "redirect"
            }
            
    except Exception as e:
        logger.error(f"Error in classify_user_input: {str(e)}", exc_info=True)
        # On error, proceed with the question as-is (failsafe)
        return {
            "messages": messages, 
            "user_level": user_level, 
            "next": "proceed"
        }


def expand_ambiguous_question(state: AgentState) -> Dict[str, Any]:
    """
    Clarify ambiguous questions by resolving references and adding context.
    
    Args:
        state: Current state containing messages and user level
        
    Returns:
        Updated state with clarified question
    """
    logger.info("Expanding ambiguous question")
    messages = state["messages"]
    current_question = messages[-1].content
    
    # Get conversation context
    conversation_context = format_conversation_context(messages)
    
    try:
        llm = get_llm(temperature=0)
        
        # First, determine if the question needs clarification at all
        assessment_prompt = PromptTemplate(
            template="""
Analyze this question in the context of a Data Structures and Algorithms conversation.

Current question: {question}

Does this question:
1. Contain any unclear pronouns (it, they, this, that) without clear referents?
2. Reference a specific DSA concept without naming it explicitly?
3. Lack sufficient specificity to be answered properly?

Respond with a simple Yes or No.
""",
            input_variables=["context", "question"]
        )
        
        needs_clarification_response = llm.invoke([
            HumanMessage(content=assessment_prompt.format(
                context=conversation_context,
                question=current_question
            ))
        ])
        
        # If no clarification needed, return original messages
        if "no" in needs_clarification_response.content.lower():
            logger.info("No clarification needed")
            return {
                "messages": messages,
                "user_level": state["user_level"]
            }
        
        # Otherwise proceed with actual clarification
        clarification_prompt = PromptTemplate(
            template="""
You are a DSA question processor. Transform user's prompt into clear, context-aware queries.

OBJECTIVE: Rewrite user's prompt to include relevant context from chat history while maintaining original intent.

Previous conversation:
{context}

Current question: {question}

TRANSFORMATION RULES:
1. Replace pronouns with specific references
   Before: "How do I implement it?"
   After: "How do I implement a binary search tree?"

2. Include relevant context
   Before: "What about the time complexity?"
   After: "What is the time complexity of quicksort's partitioning step?"

3. Maintain technical precision
   Before: "How does the fast one work?"
   After: "How does the O(n log n) merge sort algorithm work?"

4. Keep original meaning
   Do NOT add assumptions or change the question's scope

Your response should be ONLY the clarified question with no additional explanation.
""",
            input_variables=["context", "question"]
        )
        
        clarified_response = llm.invoke([
            HumanMessage(content=clarification_prompt.format(
                context=conversation_context,
                question=current_question
            ))
        ])
        
        clarified_question = clarified_response.content.strip()
        
        # If the clarified question is significantly different, use it
        if clarified_question and clarified_question != current_question:
            logger.info(f"Question clarified: '{current_question}' -> '{clarified_question}'")
            return {
                "messages": [HumanMessage(content=clarified_question)], 
                "user_level": state["user_level"]
            }
        else:
            logger.info("No meaningful clarification produced")
            return {
                "messages": messages, 
                "user_level": state["user_level"]
            }
            
    except Exception as e:
        logger.error(f"Error in expand_ambiguous_question: {str(e)}", exc_info=True)
        # On error, proceed with original question
        return {
            "messages": messages, 
            "user_level": state["user_level"]
        }


def evaluate_and_retrieve(state: AgentState) -> Dict[str, Any]:
    """
    Generate a response or use tools to retrieve information based on the query.
    
    Args:
        state: Current state containing messages and user level
        
    Returns:
        Updated state with response or tool invocation
    """
    logger.info("Evaluating query and deciding whether to retrieve documents")
    messages = state["messages"]
    
    # System message for confidence-based retrieval
    system_message = """You are a DSA expert assistant specializing in both Data Structures and Algorithms. For every question:

1. First, assess if you need additional reference information:
   - Do you need specific implementation details for a data structure or algorithm?
   - Do you need exact complexity analysis or algorithmic proofs?
   - Do you need specific examples or edge cases?
   - Do you need detailed comparison between different algorithms or data structures?

2. Based on the assessment:
   - Use the retrieve_documents tool if you need specific details
   - Base your answer on the retrieved information when used
   - Provide direct answers when appropriate

3. Response guidelines:
   - Be clear and concise
   - Focus on accuracy and completeness
   - Provide examples when helpful
   - Use appropriate technical depth for the user's level
   - Balance explanations between theoretical concepts and practical implementations
   - For algorithms, always discuss time and space complexity

Remember: Always prioritize providing accurate and helpful information on both data structures and algorithms."""

    # Prepare messages with system instruction
    full_messages = [
        HumanMessage(content=system_message),
        *messages
    ]
    
    try:
        # Initialize model with tools
        retriever = get_retriever()
        retriever_tool = create_retriever_tool(
            retriever,
            "retrieve_documents",
            """Search and return relevant documents based on user's query."""
        )
        
        tools = [retriever_tool]
        llm = get_llm().bind_tools(tools)
        
        # Get response
        response = llm.invoke(full_messages)
        logger.info("LLM response or tool invocation generated")
        
        return {"messages": [response]}
        
    except Exception as e:
        logger.error(f"Error in evaluate_and_retrieve: {str(e)}", exc_info=True)
        error_msg = "I'm having trouble answering that question right now. Could you please rephrase it?"
        return {"messages": [AIMessage(content=error_msg)]}


def assess_document_relevance(state: AgentState) -> Literal["generate", "rewrite"]:
    """
    Grade retrieved documents for relevance and completeness.
    
    Args:
        state: Current state containing messages and retrieval results
        
    Returns:
        Decision string: 'generate' or 'rewrite'
    """
    logger.info("Assessing document relevance")
    
    messages = state["messages"]
    
    # Extract question and retrieved content
    question = None
    for msg in messages:
        if isinstance(msg, HumanMessage):
            question = msg.content
            break
    
    if not question:
        logger.warning("No question found in messages")
        return "rewrite"
    
    retrieved_docs = messages[-1].content
    
    if not retrieved_docs or len(retrieved_docs.strip()) < 10:
        logger.warning("Retrieved documents are empty or too short")
        return "rewrite"

    # Define the simplified grading prompt that asks for a direct decision
    prompt = PromptTemplate(
        template="""You are a DSA expert grading retrieved content for both Data Structures and Algorithms topics.
<Question>
{question}
</Question>

<Retrieved Content>
{content}
</Retrieved Content>

<Grading Criteria>
Grade this content on:
1. Relevance: Does it directly address the DSA concepts in the question?
2. Completeness: Does it cover all aspects needed for a good answer?
3. Technical Accuracy: Is the DSA information correct and precise?
4. Algorithm Coverage: Does it adequately explain algorithmic concepts if the question is about algorithms?
5. Data Structure Coverage: Does it properly explain data structure concepts if the question is about data structures?
</Grading Criteria>

Example DSA concepts to check for:
- Data structure definitions, properties, operations, and implementations
- Algorithm steps, processes, complexity, and correctness
- Time/space complexity analysis
- Implementation details and pseudocode
- Common use cases, trade-offs, and alternatives
- Comparisons between different approaches

Based on your assessment, make a decisive recommendation:
- Answer "GENERATE" if the content is good enough to generate a response (relevance > 0.6, overall quality sufficient)
- Answer "REWRITE" if the content isn't relevant or complete enough and we should try to get better content

<Output Instruction>
Your answer must be ONLY one word: either "GENERATE" or "REWRITE".
</Output Instruction>
""",
        input_variables=["question", "content"]
    )

    try:
        # Initialize model with lower temperature for consistent grading
        llm = get_llm(temperature=0)
        
        # Get direct decision
        response = llm.invoke([
            HumanMessage(content=prompt.format(
                question=question,
                content=retrieved_docs
            ))
        ])
        
        decision = response.content.strip().upper()
        
        # Safeguard against unexpected responses
        if decision != "GENERATE" and decision != "REWRITE":
            logger.warning(f"Unexpected grading decision: {decision}. Defaulting to REWRITE")
            return "rewrite"
        
        logger.info(f"Document assessment: {decision}")
        return decision.lower()  # Convert to lowercase to match expected return values

    except Exception as e:
        logger.error(f"Error in assess_document_relevance: {str(e)}", exc_info=True)
        # On error, default to rewrite for safety
        return "rewrite"


def optimize_query(state: AgentState) -> Dict[str, Any]:
    """
    Reformulate the query to get better search results.
    
    Args:
        state: Current state containing messages
        
    Returns:
        Updated state with reformulated query
    """
    logger.info("Optimizing query")
    messages = state["messages"]
    
    # Find the original question
    question = None
    for msg in messages:
        if isinstance(msg, HumanMessage):
            question = msg.content
            break
    
    if not question:
        logger.warning("No question found to optimize")
        return {"messages": messages}

    try:
        prompt = f"""
Look at the input and try to reason about the underlying semantic intent / meaning.

Here is the initial question:
-------
{question} 
-------

Formulate an improved question that will yield better search results for Data Structures and Algorithms concepts. 
Make it more specific, include relevant technical terms, and focus on the core DSA concept being asked about.
"""

        # Generate improved question
        llm = get_llm(temperature=0)
        response = llm.invoke([HumanMessage(content=prompt)])
        logger.info(f"Query optimized: '{question}' -> '{response.content}'")
        
        return {"messages": [HumanMessage(content=response.content)]}
        
    except Exception as e:
        logger.error(f"Error in optimize_query: {str(e)}", exc_info=True)
        # On error, return original messages
        return {"messages": messages}


def synthesize_response(state: AgentState) -> Dict[str, Any]:
    """
    Generate a tailored response based on user level and retrieved content.
    
    Args:
        state: Current state containing messages and user level
        
    Returns:
        Updated state with final response
    """
    logger.info("Synthesizing response")
    messages = state["messages"]
    user_level = state["user_level"]
    
    # Get question and retrieved docs
    question = None
    for msg in messages:
        if isinstance(msg, HumanMessage):
            question = msg.content
            
    if not question:
        logger.warning("No question found to answer")
        return {
            "messages": [AIMessage(content="I couldn't understand your question. Could you please rephrase it?")],
            "user_level": user_level
        }

    docs = messages[-1].content
    
    if not docs or len(docs.strip()) < 10:
        logger.warning("Retrieved documents too short or empty")
        return {
            "messages": [AIMessage(content="I couldn't find enough information to answer your question. Could you try asking about a different DSA concept?")], 
            "user_level": user_level
        }
        
    try:
        # Level-specific content requirements stored in a dictionary
        level_requirements = get_level_requirements(user_level)
        
        prompt = PromptTemplate(
            input_variables=['context', 'question', 'level_requirements'], 
            template="""
Generate a DSA explanation following these exact requirements:

{level_requirements}

Use this reference material: "{context}"

Question: {question}

Generate response following the exact structure and constraints above.
            """
        )
        
        llm = get_llm(temperature=0)
        chain = prompt | llm | StrOutputParser()
        
        response = chain.invoke({
            "context": docs,
            "question": question,
            "level_requirements": level_requirements
        })
        
        logger.info(f"Generated response for user level: {user_level}")
        
        return {
            "messages": [AIMessage(content=response)], 
            "user_level": user_level
        }
        
    except Exception as e:
        logger.error(f"Error in synthesize_response: {str(e)}", exc_info=True)
        return {
            "messages": [AIMessage(content="I'm having trouble generating a response. Could you try rephrasing your question?")], 
            "user_level": user_level
        }


def get_level_requirements(user_level: str) -> str:
    """
    Get content requirements specific to user level.
    
    Args:
        user_level: User's competency level (beginner, intermediate, advanced)
        
    Returns:
        String containing level-specific content requirements
    """
    level_requirements = {
        "beginner": """
            REQUIRED CONTENT STRUCTURE FOR BEGINNER LEVEL:
            1. Simple definition using everyday analogies
            2. Basic step-by-step explanation with a small example (max 5 elements)
            3. Very basic time complexity (just "fast" or "slow" for different scenarios)
            4. ONE simple real-world application
            5. No implementation details unless specifically asked
            6. Avoid technical jargon - use simple terms
            7. If explaining an algorithm, include a simple walkthrough with a concrete example
            8. If explaining a data structure, clearly describe what it is and what it's used for
            
            TONE AND STYLE:
            - Use simple, clear language
            - Break complex ideas into small steps
            - Focus on building intuition
            - Limit mathematical notation
            - Use visual descriptions where helpful
            Maximum response length: 250 words
        """,
        
        "intermediate": """
            REQUIRED CONTENT STRUCTURE FOR INTERMEDIATE LEVEL:
            1. Technical definition with implementation overview
            2. Detailed step-by-step explanation with medium example (5-10 elements)
            3. Time/space complexity with basic explanation
            4. Common use cases and trade-offs
            5. Basic pseudocode if relevant
            6. Technical terms with brief explanations
            7. For algorithms: Include implementation considerations and optimization strategies
            8. For data structures: Explain operations, common implementations, and efficiency
            
            TONE AND STYLE:
            - Balance technical and plain language
            - Include some implementation details
            - Explain why certain choices are made
            - Use some mathematical notation
            - Compare with alternative approaches where relevant
            Maximum response length: 400 words
        """,
        
        "advanced": """
            REQUIRED CONTENT STRUCTURE FOR ADVANCED LEVEL:
            1. Precise technical definition with implementation considerations
            2. In-depth analysis with complex examples
            3. Detailed time/space complexity analysis with proofs if relevant
            4. Edge cases and optimization techniques
            5. Implementation variations and trade-offs
            6. Advanced applications and modifications
            7. For algorithms: Include theoretical foundations, variants, and comparative analysis
            8. For data structures: Discuss advanced operations, mathematical properties, and specialized uses
            
            TONE AND STYLE:
            - Use technical terminology freely
            - Focus on optimization and efficiency
            - Include mathematical proofs when relevant
            - Discuss system-level considerations
            - Reference related research or theoretical concepts
            Maximum response length: 600 words
        """
    }
    
    # Default to intermediate if level unknown
    return level_requirements.get(user_level.lower(), level_requirements["intermediate"])


# ===== Graph Setup =====

def create_retrieval_graph() -> StateGraph:
    """
    Create and configure the retrieval workflow graph.
    
    Returns:
        Configured StateGraph ready for compilation
    """
    logger.info("Setting up retrieval workflow graph")
    
    # Initialize retriever for the tool node
    retriever = get_retriever()
    retriever_tool = create_retriever_tool(
        retriever,
        "retrieve_documents",
        """Search and return relevant documents based on user's query."""
    )
    
    # Create state graph with schema
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("classify_user_input", classify_user_input)
    workflow.add_node("expand_ambiguous_question", expand_ambiguous_question)
    workflow.add_node("evaluate_and_retrieve", evaluate_and_retrieve)
    workflow.add_node("retrieve", ToolNode([retriever_tool]))
    workflow.add_node("synthesize_response", synthesize_response)
    workflow.add_node("optimize_query", optimize_query)
    
    # Add edges
    workflow.add_edge(START, "classify_user_input")
    
    # Conditional edges from classification
    workflow.add_conditional_edges(
        "classify_user_input",
        lambda x: x["next"],
        {
            "proceed": "evaluate_and_retrieve",
            "clarify": "expand_ambiguous_question",
            "redirect": END
        }
    )
    
    # After clarification, go to agent
    workflow.add_edge("expand_ambiguous_question", "evaluate_and_retrieve")
    
    # Tool handling
    workflow.add_conditional_edges(
        "evaluate_and_retrieve",
        tools_condition,
        {
            "tools": "retrieve",
            END: END,
        }
    )
    
    # Document relevance assessment
    workflow.add_conditional_edges(
        "retrieve",
        assess_document_relevance,
        {
            "generate": "synthesize_response",
            "rewrite": "optimize_query",
        }
    )
    
    # Final edges
    workflow.add_edge("synthesize_response", END)
    workflow.add_edge("optimize_query", "evaluate_and_retrieve")
    
    return workflow


# Initialize the graph (to be compiled by the calling code)
text_workflow = create_retrieval_graph()