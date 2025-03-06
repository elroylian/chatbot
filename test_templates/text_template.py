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
from pydantic import BaseModel, Field, field_validator
from langgraph.prebuilt import ToolNode, tools_condition 
from langgraph.graph.message import add_messages
from langgraph.graph import END, StateGraph, START

import streamlit as st
from utils.chunk_doc import get_retriever
from utils.model import get_llm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants for prompts
LANGUAGE_CHECK_PROMPT = """Analyze ONLY the current input for language:

Current input: {question}

Determine if this input contains ANY non-English text or characters.
Return:
1. message_type: 'non_english' if ANY non-English content is present, 'english' if input is entirely in English
2. response: "I can only communicate in English. Please rephrase your question in English." for non-English content"""

CONTENT_CLASSIFICATION_PROMPT = """Classify the user's intent based on their input in a DSA (Data Structures and Algorithms) chatbot context.

Previous conversation:
{context}

Current input: {question}

Classify the intent into ONE of these categories:
- dsa: Questions about data structures, algorithms, complexity analysis, implementation, or problem-solving
- pleasantry: Greetings, thanks, goodbyes, or conversational acknowledgments
- other: Non-DSA technical questions or topics outside the scope of DSA

For pleasantries: Respond naturally like a friendly tutor
For other: Tell user that it is out of your scope and redirect them to ask about DSA while being encouraging

Return:
1. message_type: 'dsa', 'pleasantry', or 'other'
2. response: Appropriate response for non-DSA inputs"""

QUESTION_ASSESSMENT_PROMPT = """
Analyze this question in the context of a Data Structures and Algorithms conversation.

Current question: {question}

Does this question:
1. Contain any unclear pronouns (it, they, this, that) without clear referents?
2. Reference a specific DSA concept without naming it explicitly?
3. Lack sufficient specificity to be answered properly?

Respond with a simple Yes or No.
"""

QUESTION_CLARIFICATION_PROMPT = """
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
"""

RETRIEVAL_PROMPT = """You are a knowledgeable DSA expert assistant specializing in Data Structures and Algorithms. Your responses must be accurate, clear, and tailored to the user's expertise (beginner, intermediate, or advanced). For every question, follow these steps:

1. **Assess Information Needs**  
   - Determine if additional reference details are required, such as:
     - Specific implementation examples or pseudocode.
     - Detailed time/space complexity analysis or proofs.
     - Concrete examples or edge cases.
     - Comparisons between alternative algorithms or data structures.

2. **Utilize Resources Effectively**  
   - If specific details are needed, use the `retrieve_documents` tool to fetch relevant information.
   - Integrate the retrieved information to enhance the accuracy and clarity of your answer.
   - Provide a direct answer when additional references are unnecessary.

3. **Response Guidelines**  
   - Be clear, concise, and focused on accuracy.
   - Use language appropriate to the user’s level, avoiding unnecessary jargon for beginners.
   - Include examples, code snippets, or pseudocode when they aid understanding.
   - Balance theoretical concepts with practical implementation details.
   - Always discuss time and space complexity for algorithm-related questions.

Remember: Your top priority is to deliver precise, helpful, and context-aware DSA explanations that empower users to understand and solve problems effectively."""

DOCUMENT_GRADING_PROMPT = """You are a DSA expert grading retrieved content for both Data Structures and Algorithms topics.
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
"""

QUERY_OPTIMIZATION_PROMPT = """
Look at the input and try to reason about the underlying semantic intent / meaning.

Here is the initial question:
-------
{question} 
-------

Formulate an improved question that will yield better search results for Data Structures and Algorithms concepts. 
Make it more specific, include relevant technical terms, and focus on the core DSA concept being asked about.
"""

RESPONSE_GENERATION_PROMPT = """
You are a friendly, approachable DSA tutor who makes complex concepts accessible and engaging. Your explanations feel like a conversation with a friend, not a textbook.

<Format_Requirements>
{level_requirements}
</Format_Requirements>

<Reference_Material>
{context}
</Reference_Material>

<Question>
{question}
</Question>

Create a response that uses the Reference Material as your knowledge foundation, but delivers it in a conversational, engaging style. Your explanation should:

- Use natural language and a friendly, supportive tone
- Include conversational phrases and transitions between concepts
- Relate technical concepts to intuitive examples when possible
- Avoid overly formal or academic language unless needed for precision
- Use "you" and "we" to create a sense of connection with the learner
- Express enthusiasm about interesting aspects of the concept

While following the format requirements for the user's level, ensure your explanation sounds like it's coming from a helpful tutor rather than an algorithm. Maintain technical accuracy from the Reference Material, but present it in a way that feels natural and engaging.

Remember to balance being conversational with being clear and precise - technical accuracy matters, but so does being relatable and easy to understand.
"""

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


# ===== Utility Functions =====

def format_conversation_context(messages: List[BaseMessage], max_messages: int = 6) -> str:
    """
    Format conversation context from messages
    
    Args:
        messages: List of conversation messages
        max_messages: Maximum number of recent messages to include
        
    Returns:
        Formatted conversation text
    """
    context_messages = messages[-max_messages:-1] if len(messages) > max_messages else messages[:-1]
    return "\n".join([
        f"{'User: ' if isinstance(m, HumanMessage) else 'Assistant: '}{m.content}"
        for m in context_messages
    ])


def get_message_content(message):
    """
    Safely extract text content from a message that might have different formats
    
    Args:
        message: The message to extract content from
        
    Returns:
        String content of the message
    """
    if isinstance(message.content, str):
        return message.content
    elif isinstance(message.content, list):
        # For multimodal content
        text_parts = []
        for item in message.content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        return " ".join(text_parts)
    return str(message.content)


def handle_workflow_error(e: Exception, messages, user_level, step_name="workflow", default_next="end"):
    """
    Centralized error handling for workflow nodes
    
    Args:
        e: The exception that occurred
        messages: Current message list
        user_level: Current user level
        step_name: Name of the step where error occurred
        default_next: Default next step
        
    Returns:
        Error response state
    """
    logger.error(f"Error in {step_name}: {str(e)}", exc_info=True)
    return {
        "messages": [*messages, AIMessage(content="I'm having trouble processing that. Could you try again?")],
        "user_level": user_level,
        "next": default_next
    }


# ===== Node Functions =====

def check_language(question: str) -> ValidationResult:
    """
    Check if the input is in English
    
    Args:
        question: User's input text
        
    Returns:
        ValidationResult with language assessment
    """
    llm = get_llm(temperature=0.5)
    language_prompt = PromptTemplate(
        template=LANGUAGE_CHECK_PROMPT,
        input_variables=["question"]
    )
    language_chain = language_prompt | llm.with_structured_output(ValidationResult)
    return language_chain.invoke({"question": question})


def handle_non_english_input(messages, user_level):
    """
    Handle non-English input by returning appropriate response
    
    Args:
        messages: Current message list
        user_level: Current user level
        
    Returns:
        Updated state
    """
    logger.info("Non-English input detected")
    return {
        "messages": [*messages, AIMessage(content="I can only communicate in English. Please rephrase your question in English.")],
        "user_level": user_level,
        "next": "redirect"
    }


def check_content_type(context: str, question: str) -> ValidationResult:
    """
    Classify the content type of the input
    
    Args:
        context: Conversation context
        question: User's input
        
    Returns:
        ValidationResult with content classification
    """
    llm = get_llm(temperature=0.5)
    classification_prompt = PromptTemplate(
        template=CONTENT_CLASSIFICATION_PROMPT,
        input_variables=["context", "question"]
    )
    chain = classification_prompt | llm.with_structured_output(ValidationResult)
    return chain.invoke({"context": context, "question": question})


def proceed_with_dsa_query(messages, user_level):
    """
    Proceed with DSA-related query
    
    Args:
        messages: Current message list
        user_level: Current user level
        
    Returns:
        Updated state
    """
    logger.info("DSA input detected, proceeding with retrieval")
    return {
        "messages": messages, 
        "user_level": user_level, 
        "next": "proceed"
    }


def redirect_non_dsa_query(messages, user_level, response):
    """
    Redirect non-DSA query with appropriate response
    
    Args:
        messages: Current message list
        user_level: Current user level
        response: Response message for non-DSA query
        
    Returns:
        Updated state
    """
    logger.info("Non-DSA input detected, redirecting")
    return {
        "messages": [*messages, AIMessage(content=response)], 
        "user_level": user_level, 
        "next": "redirect"
    }


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
    user_level = state["user_level"]
    
    try:
        # Get user's question from the latest message
        question = get_message_content(messages[-1])
        
        # Check if current message is in English
        language_result = check_language(question)
        if language_result.message_type == "non_english":
            return handle_non_english_input(messages, user_level)
        
        # Get conversation context
        conversation_context = format_conversation_context(messages)
        
        # Classify English input
        content_result = check_content_type(conversation_context, question)
        
        if content_result.message_type == "dsa":
            return proceed_with_dsa_query(messages, user_level)
        else:
            return redirect_non_dsa_query(messages, user_level, content_result.response)
            
    except Exception as e:
        return handle_workflow_error(e, messages, user_level, "classify_user_input", "proceed")


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
    user_level = state["user_level"]
    
    try:
        # Get the current question
        current_question = get_message_content(messages[-1])
        
        # Get conversation context - specifically the last 6 messages
        # This ensures we have the most relevant recent context
        max_context_messages = 6
        context_messages = messages[-max_context_messages-1:-1] if len(messages) > max_context_messages+1 else messages[:-1]
        conversation_context = "\n".join([
            f"{'User: ' if isinstance(m, HumanMessage) else 'Assistant: '}{get_message_content(m)}"
            for m in context_messages
        ])
        
        # Initialize LLM with zero temperature for consistent output
        llm = get_llm(temperature=0)
        
        # First, determine if the question needs clarification at all
        assessment_prompt = PromptTemplate(
            template=QUESTION_ASSESSMENT_PROMPT,
            input_variables=["question"]
        )
        
        needs_clarification_response = llm.invoke([
            HumanMessage(content=assessment_prompt.format(question=current_question))
        ])
        
        # If no clarification needed, return original messages
        if "no" in needs_clarification_response.content.lower():
            logger.info("No clarification needed")
            return {
                "messages": messages,
                "user_level": user_level
            }
        
        # Otherwise proceed with actual clarification
        clarification_prompt = PromptTemplate(
            template=QUESTION_CLARIFICATION_PROMPT,
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
                "user_level": user_level
            }
        else:
            logger.info("No meaningful clarification produced")
            return {
                "messages": messages, 
                "user_level": user_level
            }
            
    except Exception as e:
        return handle_workflow_error(e, messages, user_level, "expand_ambiguous_question")


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
    user_level = state["user_level"]
    
    try:
        # Prepare messages with system instruction
        full_messages = [
            HumanMessage(content=RETRIEVAL_PROMPT),
            *messages
        ]
        
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
    
    try:
        # Extract question and retrieved content
        if len(messages) < 2:
            logger.warning("Not enough messages for assessment")
            return "rewrite"
            
        question = get_message_content(messages[-2])
        retrieved_docs = get_message_content(messages[-1])
        
        if not retrieved_docs or len(retrieved_docs.strip()) < 10:
            logger.warning("Retrieved documents are empty or too short")
            return "rewrite"
    
        # Initialize model with lower temperature for consistent grading
        llm = get_llm(temperature=0)
        
        # Create grading prompt
        prompt = PromptTemplate(
            template=DOCUMENT_GRADING_PROMPT,
            input_variables=["question", "content"]
        )
        
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
        return "generate" if decision == "GENERATE" else "rewrite"

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
    
    try:
        # Find the original question
        if not messages:
            logger.warning("No messages found to optimize")
            return {"messages": messages}
            
        question = get_message_content(messages[-1])
        
        # Create optimization prompt
        prompt = PromptTemplate(
            template=QUERY_OPTIMIZATION_PROMPT,
            input_variables=["question"]
        )
    
        # Generate improved question
        llm = get_llm(temperature=0)
        response = llm.invoke([
            HumanMessage(content=prompt.format(question=question))
        ])
        
        optimized_question = response.content.strip()
        logger.info(f"Query optimized: '{question}' -> '{optimized_question}'")
        
        return {"messages": [HumanMessage(content=optimized_question)]}
        
    except Exception as e:
        return handle_workflow_error(e, messages, state["user_level"], "optimize_query")


def get_level_requirements(user_level: str) -> str:
    """
    Get improved content requirements specific to user level.
    
    Args:
        user_level: User's competency level (beginner, intermediate, advanced)
        
    Returns:
        String containing level-specific content requirements
    """
    level_requirements = {
    "beginner": """
        When explaining to a beginner:

        Start with a friendly, simple explanation that relates to everyday experiences. Think of how you'd explain it to a friend with no technical background.
        
        Include:
        • A simple, relatable definition with real-world analogies
        • A step-by-step walkthrough using a small example (3-5 elements)
        • Visual descriptions that help them "see" the concept
        • Plain language explanations of why this matters and when it's useful
        • Very simple code examples with clear comments if needed
        
        Remember that beginners need to build confidence! Point out common mistakes in a supportive way, and connect this concept to what they might already know.
        
        Keep your explanation friendly, encouraging, and under 350 words.
    """,
    
    "intermediate": """
        For intermediate learners:
        
        Build on their existing knowledge with a balance of practical implementation and theoretical understanding. They're ready for more depth but still appreciate clear guidance.
        
        Include:
        • A precise definition with proper terminology
        • A walkthrough of common implementation approaches with their trade-offs
        • A moderately complex example that shows the concept in action
        • Time and space complexity analysis with intuitive explanations
        • Practical code examples or pseudocode for key operations
        • Discussion of common optimization techniques
        
        Connect this concept to related DSA topics they likely know, and highlight when this approach would be better than alternatives they might be familiar with.
        
        Your explanation should be conversational but technically sound, around 400-550 words.
    """,
    
    "advanced": """
        For advanced learners:
        
        Provide a technically rich exploration that respects their expertise while still being engaging. They appreciate depth, mathematical rigor, and discussions of edge cases.
        
        Include:
        • Precise technical definitions with formal properties
        • In-depth analysis of implementation variations and their performance characteristics
        • Discussion of optimization techniques and their mathematical foundations
        • Connections to broader algorithmic paradigms and computer science principles
        • Analysis of edge cases and their handling
        • System-level considerations that affect real-world performance
        
        While being technically comprehensive, maintain a collegial tone that respects their expertise without being overly formal. Feel free to reference research or advanced applications when relevant.
        
        Your explanation should be substantive but engaging, around 600-800 words.
    """
    }
    
    # Default to intermediate if level unknown
    print("LEVEL REQUIREMENT: ", user_level)
    print("LEVEL REQUIREMENT: ", level_requirements.get(user_level.lower(), level_requirements["intermediate"]))
    return level_requirements.get(user_level.lower(), level_requirements["intermediate"])


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
    
    try:
        # Get question and retrieved docs
        if len(messages) < 2:
            logger.warning("Not enough messages for synthesis")
            return {
                "messages": [AIMessage(content="I couldn't understand your question. Could you please rephrase it?")],
                "user_level": user_level
            }
            
        # Generally, second-to-last message is question, last message is retrieved docs
        question = get_message_content(messages[-2])
        docs = get_message_content(messages[-1])
        
        if not docs or len(docs.strip()) < 10:
            logger.warning("Retrieved documents too short or empty")
            return {
                "messages": [AIMessage(content="I couldn't find enough information to answer your question. Could you try asking about a different DSA concept?")], 
                "user_level": user_level
            }
            
        # Level-specific content requirements
        level_requirements = get_level_requirements(user_level)
        
        # Create response generation prompt
        prompt = PromptTemplate(
            input_variables=['context', 'question', 'level_requirements'], 
            template=RESPONSE_GENERATION_PROMPT
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
        return handle_workflow_error(e, messages, user_level, "synthesize_response")


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
        lambda x: x.get("next", "redirect"),  # Default to end if not specified
        {
            "proceed": "expand_ambiguous_question",
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
            END: "synthesize_response",
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

# graph= text_workflow.compile()