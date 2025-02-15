from langchain.tools.retriever import create_retriever_tool
from utils.chunk_doc import get_retriever
import os
import streamlit as st
from langchain import hub
from typing import Annotated, Literal, Sequence, Any, Dict
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate, ChatMessagePromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langgraph.prebuilt import tools_condition
from langgraph.graph.message import add_messages
from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import ToolNode

# TODO
# Keep testing!
# Change clarification method

# Initialize the retriever
print("Initializing retriever...")
retriever = get_retriever()

# Create the retriever tool
retriever_tool = create_retriever_tool(
    retriever,
    "retrieve_documents",
    """Search and return relevant documents based on user's query."""
)

# Add the retriever tool to the list of tools
tools = [retriever_tool]

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_level: str

def classify_user_input(state) -> dict[str, Any]:
    """Validates input to handle DSA questions, ensuring English-only interaction."""
    messages = state["messages"]
    question = messages[-1].content
    user_level = state["user_level"]
    
    
    class ValidationResult(BaseModel):
        message_type: str = Field(description="Type of message: 'dsa', 'pleasantry', 'non_english', or 'other'")
        response: str = Field(description="Response for non-DSA inputs")

    # First, check if current message is non-English
    language_prompt = PromptTemplate(
        template="""Analyze ONLY the current input for language:

Current input: {question}

Determine if this input contains ANY non-English text or characters.
Return:
1. message_type: 'non_english' if ANY non-English content is present, 'english' if input is entirely in English
2. response: "I can only communicate in English. Please rephrase your question in English." for non-English content""",
        input_variables=["question"]
    )
    
    try:
        model = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.5, streaming=True, api_key=st.secrets["OpenAI_key"])
        language_chain = language_prompt | model.with_structured_output(ValidationResult)
        language_result = language_chain.invoke({"question": question})
        
        # If non-English is detected, return immediately
        if language_result.message_type == "non_english":
            return {
                "messages": [*messages, AIMessage(content="I can only communicate in English. Please rephrase your question in English.")],
                "user_level": user_level,
                "next": "redirect"
            }
            
        # If message is in English, proceed with full classification
        context_messages = messages[-6:-1] if len(messages) > 6 else messages[:-1]
        conversation_context = "\n".join([f"{'User: ' if isinstance(m, HumanMessage) else 'Assistant: '}{m.content}" 
                                        for m in context_messages])
        
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
For other: Redirect to DSA while being encouraging

Return:
1. message_type: 'dsa', 'pleasantry', or 'other'
2. response: Appropriate response for non-DSA inputs""",
            input_variables=["context", "question"]
        )
        
        chain = classification_prompt | model.with_structured_output(ValidationResult)
        result = chain.invoke({"context": conversation_context, "question": question})
        
        if result.message_type == "dsa":
            return {"messages": messages, "user_level": user_level, "next": "proceed"}
        else:
            return {"messages": [*messages, AIMessage(content=result.response)], 
                    "user_level": user_level, 
                    "next": "redirect"}
            
    except Exception as e:
        print(f"Validation error: {str(e)}")
        return {"messages": messages, "user_level": user_level, "next": "proceed"}

def expand_ambiguous_question(state):
    """
    Clarifies ambiguous questions by maintaining conversation context,
    with improved handling of pronoun references to DSA concepts.
    """
    print("\n=== CLARIFY NODE ===")
    messages = state["messages"]
    current_question = messages[-1].content
    print(f"Original question: {current_question}")
    
    # Get the last 3 exchanges (up to 6 messages) for relevant context
    context_messages = messages[-6:-1] if len(messages) > 6 else messages[:-1]
    conversation_context = "\n".join([
        f"{'User: ' if isinstance(m, HumanMessage) else 'Assistant: '}{m.content}"
        for m in context_messages
    ])
    
    class ClarificationResult(BaseModel):
        clarified_question: str = Field(
            description="The clarified version of the question with pronouns replaced by their referents",
            default=""  # Provide empty string as default
        )
        referenced_concept: str = Field(
            description="The main DSA concept being referenced from previous context",
            default=""  # Provide empty string as default
        )
    
    model = ChatOpenAI(
        model_name="gpt-4o-mini", 
        temperature=0, 
        streaming=True, 
        api_key=st.secrets["OpenAI_key"]
    )
    llm_with_clarification = model.with_structured_output(ClarificationResult)
    
    prompt = PromptTemplate(
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

Return ONLY the reformulated question without explanation.

""",
        input_variables=["context", "question"]
    )
    
    chain = prompt | llm_with_clarification
    
    try:
        result = chain.invoke({
            "context": conversation_context,
            "question": current_question
        })
        
        # For non-DSA questions or greetings, use original question
        if not result.needs_clarification:
            print("No clarification needed - using original question")
            return {"messages": messages, "user_level": state["user_level"]}
            
        # For questions needing clarification, verify we have the clarified version
        if result.needs_clarification and result.clarified_question:
            print(f"Referenced concept: {result.referenced_concept}")
            print(f"Clarified to: {result.clarified_question}")
            return {"messages": [HumanMessage(content=result.clarified_question)], "user_level": state["user_level"]}
        else:
            print("No clarification needed")
            return {"messages": messages, "user_level": state["user_level"]}
            
    except Exception as e:
        print(f"Error in clarification: {str(e)}")
        # On error, proceed with original question
        return {"messages": messages, "user_level": state["user_level"]}
    

def evaluate_and_retrieve(state):
    """
    Invokes the agent model to generate a response based on confidence level.
    
    Args:
        state (messages): The current state

    Returns:
        dict: The updated state with the agent response appended to messages
    """
    print("---CALL AGENT---")
    messages = state["messages"]
    
    # System message that enforces confidence-based retrieval
    system_message = """You are a DSA expert assistant. For every question:

1. First, assess if you need additional reference information:
   - Do you need specific implementation details?
   - Do you need exact complexity analysis?
   - Do you need specific examples or edge cases?

2. Based on the assessment:
   - Use the retrieve_documents tool if you need specific details
   - Base your answer on the retrieved information when used
   - Provide direct answers when appropriate

3. Response guidelines:
   - Be clear and concise
   - Focus on accuracy and completeness
   - Provide examples when helpful
   - Use appropriate technical depth for the user's level

Remember: Always prioritize providing accurate and helpful information."""

    # Prepare messages with system instruction
    full_messages = [
        HumanMessage(content=system_message),
        *messages
    ]
    
    # Initialize model with tools
    model = ChatOpenAI(temperature=0, model="gpt-4o-mini", streaming=True, api_key=st.secrets["OpenAI_key"])
    model = model.bind_tools(tools)
    
    # Get response
    response = model.invoke(full_messages)
    
    return {"messages": [response]}

def assess_document_relevance(state) -> Literal["generate", "rewrite"]:
    """
    Enhanced grading system for retrieved DSA documents.
    
    Evaluates:
    1. Relevance to the question
    2. Completeness of the answer
    3. Technical accuracy
    4. Need for clarification
    
    Returns:
    - "generate": When documents are good enough to generate response
    - "rewrite": When documents aren't relevant enough
    - "clarify": When question needs clarification
    """
    print("---ENHANCED GRADING SYSTEM---")
    
    class GradeResult(BaseModel):
        relevance_score: float = Field(description="0-1 score for topic relevance")
        completeness_score: float = Field(description="0-1 score for answer completeness")
        technical_accuracy: float = Field(description="0-1 score for technical accuracy")
        reasoning: str = Field(description="Explanation for the grading decision")

    messages = state["messages"]
    question = messages[0].content
    retrieved_docs = messages[-1].content

    # Define the grading prompt
    prompt = PromptTemplate(
        template="""You are a DSA expert grading retrieved content.

Question: {question}

Retrieved Content:
{content}

Grade this content on:
1. Relevance: Does it directly address the DSA concepts in the question?
2. Completeness: Does it cover all aspects needed for a good answer?
3. Technical Accuracy: Is the DSA information correct and precise?
4. Clarity: Is the question clear or needs clarification?

Example DSA concepts to check for:
- Data structure definitions and properties
- Algorithm steps and processes
- Time/space complexity mentions
- Implementation details
- Common use cases and examples

Return scores as decimals between 0 and 1, where:
- 0.0-0.3: Poor
- 0.4-0.6: Moderate
- 0.7-1.0: Good

Also explain your reasoning.""",
        input_variables=["question", "content"]
    )

    try:
        # Initialize model with lower temperature for consistent grading
        model = ChatOpenAI(
            model_name="gpt-4o-mini",
            temperature=0,
            streaming=True,
            api_key=st.secrets["OpenAI_key"]
        )
        
        # Grade with structured output
        chain = prompt | model.with_structured_output(GradeResult)
        result = chain.invoke({
            "question": question,
            "content": retrieved_docs
        })
        
        print(f"Grading Results:\n"
              f"Relevance: {result.relevance_score:.2f}\n"
              f"Completeness: {result.completeness_score:.2f}\n"
              f"Technical Accuracy: {result.technical_accuracy:.2f}\n")
            
        # Calculate weighted average score
        weighted_score = (
            result.relevance_score * 0.4 +      # Relevance is most important
            result.completeness_score * 0.3 +    # Completeness next
            result.technical_accuracy * 0.3      # Technical accuracy equally important
        )
        
        # Decision thresholds
        GOOD_THRESHOLD = 0.65
        
        if weighted_score >= GOOD_THRESHOLD:
            print("---DECISION: CONTENT GOOD ENOUGH TO GENERATE---")
            return "generate"
        else:
            print("---DECISION: NEED TO REWRITE QUERY---")
            return "rewrite"

    except Exception as e:
        print(f"Grading error: {str(e)}")
        # On error, default to rewrite for safety
        return "rewrite"
    
def optimize_query(state):
    """
    Transform the query to produce a better question.

    Args:
        state (messages): The current state

    Returns:
        dict: The updated state with re-phrased question
    """

    print("---TRANSFORM QUERY---")
    messages = state["messages"]
    question = messages[0].content

    msg = [
        HumanMessage(
            content=f""" \n 
    Look at the input and try to reason about the underlying semantic intent / meaning. \n 
    Here is the initial question:
    \n ------- \n
    {question} 
    \n ------- \n
    Formulate an improved question: """,
        )
    ]

    # Grader
    model = ChatOpenAI(temperature=0, model="gpt-4o-mini", streaming=True,api_key=st.secrets["OpenAI_key"])
    response = model.invoke(msg)
    return {"messages": [response]}

def synthesize_response(state):
    """Generate response based on retrieved content and question with strong user level differentiation"""
    print("\n=== GENERATE RESPONSE ===")
    messages = state["messages"]
    user_level = state["user_level"]
    
    # Get last question
    question = None
    for msg in messages:
        if isinstance(msg, HumanMessage):
            question = msg.content
            
    if not question:
        return {
            "messages": [AIMessage(content="Please rephrase your question.")],
            "user_level": user_level
        }

    docs = messages[-1].content
    
    if not docs or len(docs.strip()) < 10:
        return {
            "messages": [AIMessage(content="Please rephrase your question for more relevant results.")], 
            "user_level": user_level
        }
        
    try:
        llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0, streaming=True, api_key=st.secrets["OpenAI_key"])
        
        # Level-specific content requirements
        level_requirements = {
            "beginner": """
                REQUIRED CONTENT STRUCTURE FOR BEGINNER LEVEL:
                1. Simple definition using everyday analogies
                2. Basic step-by-step explanation with a small example (max 5 elements)
                3. Very basic time complexity (just "fast" or "slow" for different scenarios)
                4. ONE simple real-world application
                5. No implementation details unless specifically asked
                6. Avoid technical jargon - use simple terms
                
                TONE AND STYLE:
                - Use simple, clear language
                - Break complex ideas into small steps
                - Focus on building intuition
                - Limit mathematical notation
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
                
                TONE AND STYLE:
                - Balance technical and plain language
                - Include some implementation details
                - Explain why certain choices are made
                - Use some mathematical notation
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
                
                TONE AND STYLE:
                - Use technical terminology freely
                - Focus on optimization and efficiency
                - Include mathematical proofs when relevant
                - Discuss system-level considerations
                Maximum response length: 600 words
            """
        }

        print("\nDebug user level: ", user_level.lower())
        
        # Get appropriate requirements for user level
        level_specific_requirements = level_requirements.get(
            user_level.lower(), 
            level_requirements["intermediate"]  # Default to intermediate if level unknown
        )
        
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
        
        chain = prompt | llm | StrOutputParser()
        response = chain.invoke({
            "context": docs,
            "question": question,
            "level_requirements": level_specific_requirements
        })
        
        return {"messages": [AIMessage(content=response)], "user_level": user_level}
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "messages": [AIMessage(content="Please try rephrasing your question.")], 
            "user_level": user_level
        }

################################################################################################################
# Graph setup
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("classify_user_input", classify_user_input)
workflow.add_node("expand_ambiguous_question", expand_ambiguous_question)
workflow.add_node("evaluate_and_retrieve", evaluate_and_retrieve)
retrieve = ToolNode([retriever_tool])
workflow.add_node("retrieve", retrieve)
workflow.add_node("synthesize_response", synthesize_response)
workflow.add_node("optimize_query", optimize_query)

# Add edges
workflow.add_edge(START, "classify_user_input")

# Modify validation to return three possible outcomes
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

workflow.add_conditional_edges(
    "evaluate_and_retrieve",
    tools_condition,
    {
        "tools": "retrieve",
        END: END,
    }
)

workflow.add_conditional_edges(
    "retrieve",
    assess_document_relevance,
    {
        "generate": "synthesize_response",
        "rewrite": "optimize_query",
    }
)

workflow.add_edge("synthesize_response", END)
workflow.add_edge("optimize_query", "evaluate_and_retrieve")

# Compile graph
from test_templates.memory import memory
graph = workflow.compile(memory)
