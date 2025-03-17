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
- dsa: Questions about data structures, algorithms, complexity analysis, implementation, problem-solving, or anything related to dsa
- pleasantry: Greetings, thanks, goodbyes or conversational acknowledgments
- other: Non-DSA questions or topics outside the scope of DSA

For pleasantries: Respond naturally like a friendly tutor
For other: Tell user that it is out of your scope and redirect them to ask about DSA while being encouraging

Return:
1. message_type: 'dsa', 'pleasantry', or 'other'
2. response: Appropriate response for non-DSA inputs"""

# Consolidated Question Clarification Prompt
QUESTION_CLARIFICATION_PROMPT = """
You are a specialized DSA question processor working with a conversational AI system. Your task is to transform user questions into clear, context-aware queries while preserving the original intent.

<Previous_Conversation>
{context}
</Previous_Conversation>

<Current_Question>
{question}
</Current_Question>

<Analysis_Guidelines>
- Determine if this is a new topic or a follow-up to the previous conversation.
- Assess whether the question is sufficiently clear as stated.
- Consider if the user's intent is obvious despite brevity.
- Evaluate if additional context would improve clarity.
</Analysis_Guidelines>

<Clarification_Principles>
1. Minimal intervention: Make the smallest changes needed for clarity.
2. Intent preservation: Never change what the user is asking about.
3. Natural language: Output should sound like a human question.
4. Context awareness: Use conversation history intelligently.
5. Topic boundaries: Don't carry implementation details across unrelated topics.
IMPORTANT: When users mention just an algorithm or data structure name (e.g., "insertion sort", "binary trees"), they typically want a general explanation. Transform these into natural-sounding questions that ask for an explanation, but avoid formulaic expansions that sound robotic.
</Clarification_Principles>

<Output_Requirements>
- Return a natural-sounding, clear question.
- If the original question is already clear, return it unchanged.
- Ensure the question is a complete sentence.
- Use conversation context only when necessary to resolve ambiguity.
- Never explain your reasoning - return only the clarified question.
</Output_Requirements>

Return ONLY the clarified question with no explanations or additional text.
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
- Answer "GENERATE" if the content is good enough to generate a response
- Answer "REWRITE" if the content isn't relevant or complete enough and we should try to get better content

<Output Instruction>
Your answer must be ONLY one word: either "GENERATE" or "REWRITE".
</Output Instruction>
"""

QUERY_OPTIMIZATION_PROMPT = """
Here is the initial question:
-------
{question} 
-------

Expand this into a more complete sentence that will improve retrieval results by:
1. Converting short phrases into full, grammatically complete questions
2. Including relevant DSA terminology
3. Maintaining the exact meaning and intent of the original query
4. Adding contextual DSA keywords without changing the scope

Your expanded version should be a single, well-formed question that would naturally yield better search results.
"""

RESPONSE_GENERATION_PROMPT = """
You are a friendly, conversational DSA tutor. Your responses should be natural, engaging, and carefully tailored to avoid repetition.

<Question>
{question}
</Question>

<Reference_Material>
{context}
</Reference_Material>

<User_Level>
You can use markdown formatting for better readability.
{level_requirements}
</User_Level>

<Previous_Exchanges>
{conversation_history}
</Previous_Exchanges>

<Strict_Rules>
1. NEVER repeat explanations, analogies, examples, or code from previous exchanges - this is your #1 priority
2. If you catch yourself about to repeat information, STOP and use a different approach
3. For follow-up questions about the same topic, ONLY provide the new information requested
4. Do NOT restate basic definitions or concepts you've already covered
</Strict_Rules>

<Conversation_Flow>
1. Start with a brief, friendly acknowledgment of the question 
2. For questions on topics previously discussed:
   - Use phrases like "Building on our previous discussion..." or "As we saw earlier..."
   - Reference but don't repeat the earlier explanation
   - Focus ONLY on what's new or different in this question

3. For completely new topics:
   - Use a fresh, engaging introduction
   - Provide a concise explanation with examples appropriate to user level

4. For follow-up questions (like "java code?" or "what's the time complexity?"):
   - Answer DIRECTLY without restating what was already covered
   - Use transitional phrases like "Now for the Java implementation..." or "Regarding time complexity..."

5. End with a brief, engaging closing that invites further exploration
</Conversation_Flow>

<Voice_And_Style>
- Use varied sentence structures and transitions
- Be warm and encouraging
- Speak naturally like a friendly tutor, not a textbook
- Adapt your tone to the user's level (more casual for beginners, more technical for advanced)
- Use occasional questions to engage the user
- Incorporate light humor where appropriate
</Voice_And_Style>

<Type_Specific_Instructions>
If the user asks for:
1. A different programming language implementation:
   - Say "Here's the implementation in [language]:" and ONLY show the code
   - Do NOT re-explain the algorithm logic unless specifically asked
   
2. Time/space complexity:
   - If already mentioned, just elaborate on the specific aspects asked about
   - Don't restate the full explanation
   
3. Clarification on a concept:
   - Focus narrowly on the specific confusion point
   - Reference but don't repeat previous explanations
</Type_Specific_Instructions>

Respond accordingly based on the previous exchanges, user's competency level, and the DSA content provided.
"""

DIRECT_GENERATION_PROMPT = """
You are a friendly, conversational DSA tutor. Your responses should be natural, engaging, and carefully tailored to avoid repetition. 
Respond to the question accordingly based on the previous exchanges. Only tailor to user level if its a new topic and not a follow up question.

<Question>
{question}
</Question>

<User_Level>
You can use markdown formatting for better readability.
{level_requirements}
</User_Level>

<Previous_Exchanges>
{conversation_history}
</Previous_Exchanges>


"""

# ===== Models and Type Definitions =====

class MessageState(TypedDict):
    """State schema for the retrieval workflow"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_level: str
    retrieval_attempts: Optional[int] = 0

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

def format_conversation_context(messages: List[BaseMessage], max_messages: int = 10) -> str:
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


def classify_user_input(state: MessageState) -> Dict[str, Any]:
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


def expand_ambiguous_question(state: MessageState) -> Dict[str, Any]:
    """
    Process questions by determining if they are new topics or follow-ups
    and applying appropriate clarification.
    
    Args:
        state: Current state containing messages and user level
        
    Returns:
        Updated state with processed question
    """
    logger.info("Processing question context and clarification")
    messages = state["messages"]
    user_level = state["user_level"]
    
    try:
        # Get the current question
        current_question = get_message_content(messages[-1])
        
        # Get conversation context with increased history
        max_context_messages = 10
        context_messages = messages[-max_context_messages-1:-1] if len(messages) > max_context_messages+1 else messages[:-1]
        conversation_context = "\n".join([
            f"{'User: ' if isinstance(m, HumanMessage) else 'Assistant: '}{get_message_content(m)}"
            for m in context_messages
        ])
        
        # Initialize LLM with zero temperature for consistent output
        llm = get_llm(temperature=0)
        
        # Use the consolidated clarification prompt that handles both
        # topic detection and appropriate clarification
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
        
        # If the clarified question is different from the original, use it
        if clarified_question and clarified_question != current_question:
            logger.info(f"Question processed: '{current_question}' -> '{clarified_question}'")
            return {
                "messages": [*messages[:-1], HumanMessage(content=clarified_question)], 
                "user_level": user_level
            }
        else:
            logger.info("No changes needed to question")
            return {
                "messages": messages, 
                "user_level": user_level
            }
            
    except Exception as e:
        return handle_workflow_error(e, messages, user_level, "expand_ambiguous_question")


def evaluate_and_retrieve(state: MessageState) -> Dict[str, Any]:
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
    
    # Get current attempt count or initialize to 0
    retrieval_attempts = state.get("retrieval_attempts", 0) + 1
    
    # Check if max attempts reached
    if retrieval_attempts >= 2:
        logger.warning(f"Maximum retrieval attempts reached ({retrieval_attempts-1}). Falling back to direct generation.")
        return {
            "messages": messages,
            "user_level": user_level,
            "retrieval_attempts": retrieval_attempts,
            "next": "direct_generation"  # Signal to use direct generation
        }
    
    try:
        # Update attempt counter in state
        logger.info(f"Retrieval attempt {retrieval_attempts} of 5")
        
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
        
        return {
            "messages": [response],
            "user_level": user_level,
            "retrieval_attempts": retrieval_attempts
        }
        
    except Exception as e:
        error_msg = "I'm having trouble answering that question right now. Could you please rephrase it?"
        return {"messages": [AIMessage(content=error_msg)]}


def assess_document_relevance(state: MessageState) -> Literal["generate", "rewrite"]:
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


def optimize_query(state: MessageState) -> Dict[str, Any]:
    """
    Reformulate the query to get better search results.
    
    Args:
        state: Current state containing messages
        
    Returns:
        Updated state with reformulated query
    """
    logger.info("Optimizing query")
    messages = state["messages"]
    user_level = state["user_level"]
    retrieval_attempts = state.get("retrieval_attempts", 0)
    
    try:
        # Find the original question
        if not messages:
            logger.warning("No messages found to optimize")
            return {"messages": messages}
            
        # Find the latest human message (question) to optimize
        question = None
        for i in range(len(messages) - 1, -1, -1):
            if isinstance(messages[i], HumanMessage):
                question = get_message_content(messages[i])
                break
        logger.info(f"Original query: {question}")
        
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
        # logger.info(f"Query optimized: '{question}' -> '{optimized_question}'")
        
        return {
            "messages": [HumanMessage(content=optimized_question)],
            "user_level": user_level,
            "retrieval_attempts": retrieval_attempts  # Pass counter through
        }
        
    except Exception as e:
        return handle_workflow_error(e, messages, state["user_level"], "optimize_query")


def get_level_requirements(user_level: str) -> str:
    """
    Get improved content requirements specific to user level.

    Args:
        user_level: User's competency level (beginner, intermediate, advanced)

    Returns:
        A string containing level-specific content requirements.
    """
    level_requirements = {
        "beginner": """
            When explaining to a beginner: \n
            \n
            Start with a friendly, simple explanation that relates to everyday experiences.
            Include a simple, relatable definition with real-world analogies, a step-by-step walkthrough using visual descriptions, plain language explanations of why the concept matters, and very simple code examples.\n
            Additionally, if applicable, briefly mention any performance strengths (for example, that the algorithm is especially efficient for small or nearly sorted lists and is memory-friendly).\n
            Aim for clarity and conciseness (for instance, around 350 words if it naturally fits), but prioritize ensuring the explanation is accessible and builds confidence.
        """,
        "intermediate": """
            For intermediate learners:\n
            \n
            Provide a balanced explanation that combines both practical implementation and theoretical insights.\n
            Include a precise definition with proper terminology, a walkthrough of common implementation approaches, a moderately complex example, an intuitive time/space complexity analysis, practical code examples or pseudocode, and a discussion of common optimizations.\n
            Aim for a conversational yet technically sound explanation (roughly 400-550 words is a guideline), but adjust based on the depth required.\n
        """,
        "advanced": """
            For advanced learners:\n
            \n
            Deliver a technically rich, in-depth explanation that respects their expertise.\n
            Include precise definitions with formal properties, detailed analysis of implementation variations, discussions of optimization techniques and their mathematical foundations, connections to broader algorithmic paradigms, and an analysis of edge cases.\n
            Aim for a substantive yet engaging explanation (as a guideline, around 600-800 words),while adapting as needed based on the complexity of the topic.
        """
    }
    
    selected_requirement = level_requirements.get(user_level.lower(), level_requirements["intermediate"])
    logger.debug("LEVEL REQUIREMENT: %s", user_level)
    logger.debug("Selected requirement: %s", selected_requirement)
    return selected_requirement




def synthesize_response(state: MessageState) -> Dict[str, Any]:
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
            
        # Get the current question
        question = get_message_content(messages[-2])
        docs = get_message_content(messages[-1])
        
        if not docs or len(docs.strip()) < 10:
            logger.warning("Retrieved documents too short or empty")
            return {
                "messages": [AIMessage(content="I couldn't find enough information to answer your question. Could you try asking about a different DSA concept?")], 
                "user_level": user_level
            }
        
        # Extract previous assistant messages to check for patterns
        # Only include the last 2-3 exchanges to focus on recent patterns
        previous_responses = []
        for i in range(len(messages) - 3, 0, -2):  # Start from 3 messages back, go backward, step 2
            if i >= 0 and isinstance(messages[i], AIMessage):
                previous_responses.append(get_message_content(messages[i]))
            if len(previous_responses) >= 3:  # Get at most 3 previous responses
                break
                
        conversation_history = "\n\n---\n\n".join(previous_responses)
            
        # Level-specific content requirements
        level_requirements = get_level_requirements(user_level)
        
        # Create response generation prompt
        prompt = PromptTemplate(
            input_variables=['context', 'question', 'level_requirements', 'conversation_history'], 
            template=RESPONSE_GENERATION_PROMPT
        )
        
        # Use higher temperature for more variety
        llm = get_llm(temperature=0.5)
        chain = prompt | llm | StrOutputParser()
        
        response = chain.invoke({
            "context": docs,
            "question": question,
            "level_requirements": level_requirements,
            "conversation_history": conversation_history
        })
        
        logger.info(f"Generated response for user level: {user_level}")
        
        return {
            "messages": [AIMessage(content=response)], 
            "user_level": user_level
        }
        
    except Exception as e:
        return handle_workflow_error(e, messages, user_level, "synthesize_response")

def generate_direct_response(state: MessageState) -> Dict[str, Any]:
    """
    Generate a response directly from the model's knowledge without retrieved content.
    
    Args:
        state: Current state containing messages and user level
        
    Returns:
        Updated state with generated response
    """
    logger.info("Generating direct response without retrieval")
    messages = state["messages"]
    user_level = state["user_level"]
    
    try:
        # Get the current question
        if len(messages) < 1:
            logger.warning("No messages for direct response")
            return {
                "messages": [AIMessage(content="I couldn't understand your question. Could you please rephrase it?")],
                "user_level": user_level
            }
        
        # Find the latest user question
        question = None
        for i in range(len(messages) - 1, -1, -1):
            if isinstance(messages[i], HumanMessage):
                question = get_message_content(messages[i])
                break
        
        if not question:
            logger.warning("No question found for direct response")
            return {
                "messages": [AIMessage(content="I'm not sure what you're asking. Could you please clarify your question?")],
                "user_level": user_level
            }
        
        # Extract previous assistant messages to check for patterns
        previous_responses = []
        for i in range(len(messages) - 3, 0, -2):  # Start from 3 messages back
            if i >= 0 and isinstance(messages[i], AIMessage):
                previous_responses.append(get_message_content(messages[i]))
            if len(previous_responses) >= 3:  # Get at most 3 previous responses
                break
                
        conversation_history = "\n\n---\n\n".join(previous_responses)
            
        # Level-specific content requirements
        level_requirements = get_level_requirements(user_level)
        
        # Use the same RESPONSE_GENERATION_PROMPT but with guidance for direct knowledge
        prompt = PromptTemplate(
            input_variables=['question', 'level_requirements', 'conversation_history'], 
            template=DIRECT_GENERATION_PROMPT
        )
        
        # Initialize LLM with appropriate temperature
        llm = get_llm(temperature=0.5)
        chain = prompt | llm | StrOutputParser()
        
        response = chain.invoke({
            "question": question,
            "level_requirements": level_requirements,
            "conversation_history": conversation_history
        })
        
        logger.info(f"Generated direct response for user level: {user_level}")
        
        from langchain_core.messages import RemoveMessage
        
        return {
            "messages": [AIMessage(content=response)], 
            "user_level": user_level
        }
        
    except Exception as e:
        return handle_workflow_error(e, messages, user_level, "generate_direct_response")
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
    workflow = StateGraph(MessageState)
    
    # Add nodes
    workflow.add_node("classify_user_input", classify_user_input)
    workflow.add_node("expand_ambiguous_question", expand_ambiguous_question)
    workflow.add_node("evaluate_and_retrieve", evaluate_and_retrieve)
    workflow.add_node("retrieve", ToolNode([retriever_tool]))
    workflow.add_node("synthesize_response", synthesize_response)  # For retrieval-based responses
    workflow.add_node("generate_direct_response", generate_direct_response)  # For direct knowledge responses
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
    
    # After clarification, go to retrieval or direct response generation
    workflow.add_edge("expand_ambiguous_question", "evaluate_and_retrieve")
    
    # Tool handling
    # workflow.add_conditional_edges(
    #     "evaluate_and_retrieve",
    #     tools_condition,
    #     {
    #         "tools": "retrieve",
    #         END: "generate_direct_response",
    #     }
    # )
    workflow.add_conditional_edges(
    "evaluate_and_retrieve",
        lambda x: x.get("next", tools_condition(x)),
            {
                "tools": "retrieve",
                "direct_generation": "generate_direct_response",
                END: "generate_direct_response",
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
    workflow.add_edge("generate_direct_response", END)
    workflow.add_edge("optimize_query", "evaluate_and_retrieve")
    
    return workflow


# Initialize the graph (to be compiled by the calling code)
text_workflow = create_retrieval_graph()

# graph= text_workflow.compile()