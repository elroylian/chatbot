from langchain.tools.retriever import create_retriever_tool
from utils.chunk_doc import get_retriever
import os
import streamlit as st
from langchain import hub
from typing import Annotated, Literal, Sequence
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langgraph.prebuilt import tools_condition
from langgraph.graph.message import add_messages

# Initialize the retriever
retriever = get_retriever()

# Create the retriever tool
retriever_tool = create_retriever_tool(
    retriever,
    "retrieve_documents",
    "Search and return relevant documents based on user's query.",
)

# Add the retriever tool to the list of tools
tools = [retriever_tool]

class AgentState(TypedDict):
    # The add_messages function defines how an update should be processed
    # Default is to replace. add_messages says "append"
    messages: Annotated[Sequence[BaseMessage], add_messages]
    # The user's competency level
    user_level: str

### Edges


def grade_documents(state) -> Literal["generate", "rewrite"]:
    """
    Determines whether the retrieved documents are relevant to the question.

    Args:
        state (messages): The current state

    Returns:
        str: A decision for whether the documents are relevant or not
    """

    print("---CHECK RELEVANCE---")

    # Data model
    class grade(BaseModel):
        """Binary score for relevance check."""

        binary_score: str = Field(description="Relevance score 'yes' or 'no'")

    # LLM
    model = ChatOpenAI(model_name="gpt-4o-mini", temperature=0, streaming=True)

    # LLM with tool and validation
    llm_with_tool = model.with_structured_output(grade)

    # Prompt
    prompt = PromptTemplate(
        template="""You are a grader assessing relevance of a retrieved document to a user question. \n 
        Here is the retrieved document: \n\n {context} \n\n
        Here is the user question: {question} \n
        If the document contains keyword(s) or semantic meaning related to the user question, grade it as relevant. \n
        Give a binary score 'yes' or 'no' score to indicate whether the document is relevant to the question.""",
        input_variables=["context", "question"],
    )

    # Chain
    chain = prompt | llm_with_tool

    messages = state["messages"]
    last_message = messages[-1]

    question = messages[0].content
    docs = last_message.content

    scored_result = chain.invoke({"question": question, "context": docs})

    score = scored_result.binary_score

    if score == "yes":
        print("---DECISION: DOCS RELEVANT---")
        return "generate"

    else:
        print("---DECISION: DOCS NOT RELEVANT---")
        print(score)
        return "rewrite"

def validate_dsa_question(state) -> Literal["proceed", "redirect"]:
    """
    Determines whether the question is DSA-related before proceeding with retrieval.
    
    Args:
        state (messages): The current state containing the user's question
        
    Returns:
        str: A decision for whether to proceed with the question or redirect
    """
    
    print("---VALIDATING DSA TOPIC---")
    
    # Data model for structured output
    class ValidationResult(BaseModel):
        """Binary validation for DSA-related questions."""
        is_dsa: str = Field(description="Binary 'yes' or 'no' indicating if question is DSA-related")
        explanation: str = Field(description="Brief explanation of why the question is or isn't DSA-related")
        redirect_message: str = Field(description="Polite redirect message if question isn't DSA-related")

    # LLM setup
    model = ChatOpenAI(model_name="gpt-4o-mini", temperature=0, streaming=True)
    llm_with_validation = model.with_structured_output(ValidationResult)
    
    # Validation prompt
    prompt = PromptTemplate(
        template="""You are validating whether questions or codes are related to Data Structures and Algorithms (DSA).\n
        If question is non-DSA, redirect politely to ask about DSA concepts instead.\n
        
        Question to validate: {question}\n
        Determine if this is question or code are DSA-related. If it's not, redirect user to ask about DSA concepts instead.
        """,
        input_variables=["question"]
    )
    
    # Get the user's question from state
    messages = state["messages"]
    question = messages[-1].content
    print("[validation] question asked: ", question)
    # Run validation
    chain = prompt | llm_with_validation
    result = chain.invoke({"question": question})
    
    if result.is_dsa.lower() == "yes":
        print("---DECISION: VALID DSA QUESTION---")
        return {"messages": state["messages"], "user_level": state["user_level"], "next": "proceed"}
    else:
        print("---DECISION: NON-DSA QUESTION---")
        messages = state["messages"].copy()
        messages.append(AIMessage(content=result.redirect_message))
        return {"messages": messages, "user_level": state["user_level"], "next": "redirect"}

def clarify_question(state):
    """
    Clarifies ambiguous questions like "can I have the code for it?" by looking at conversation context.
    
    Args:
        state (messages): The current state including conversation history
        
    Returns:
        dict: Updated state with clarified question if needed
    """
    print("---CLARIFYING QUESTION---")
    messages = state["messages"]
    current_question = messages[-1].content
    
    # Create context from previous messages if they exist
    conversation_context = "\n".join([
        f"{'User: ' if isinstance(m, HumanMessage) else 'Assistant: '}{m.content}"
        for m in messages[:-1]
    ])
    
    class ClarificationResult(BaseModel):
        """Determines if question needs clarification and provides clarified version."""
        needs_clarification: bool = Field(
            description="Set to true if the question contains pronouns (it, that, this), is a follow-up question, or is ambiguous. Set to false if the question is already clear and specific."
        )
        clarified_question: str = Field(
            description="Write the clarified question as if the user is asking it. Example: if user says 'yes please' after assistant asks about merge sort complexity, write 'Can you explain the time complexity of merge sort?' NOT 'Would you like me to explain merge sort complexity?'"
        )
        
    model = ChatOpenAI(model_name="gpt-4o-mini", temperature=0, streaming=True)
    llm_with_clarification = model.with_structured_output(ClarificationResult)
    
    prompt = PromptTemplate(
        template="""You are helping clarify user questions while maintaining their perspective.

    Previous conversation:
    {context}

    Current question: {question}

    First determine if the question needs clarification. A question needs clarification ONLY if ALL these conditions are met:
    1. The previous conversation contains specific DSA topics (like sorting, trees, graphs, etc.)
    2. The current question is ambiguous or uses pronouns (it, that, this)
    3. There's enough context to make a meaningful clarification

    Do NOT clarify if:
    1. The previous message was just a greeting or general invitation to ask questions
    2. There's no specific DSA topic being discussed yet
    3. The clarification would still be too generic

    IMPORTANT: When clarifying, always write from USER's perspective:

    Good examples (DO THESE):
    User: "yes" (after assistant asks about BST implementation)
    ✓ Clarified as: "Can you show me how to implement a binary search tree?"

    Special cases (DON'T CLARIFY):
    - If the previous message was a general greeting or open invitation
    - If there's no specific DSA topic in the previous context
    - If the question is the first message in a conversation

    User: "what about complexity?"
    ✓ Clarified as: "What's the time complexity of quicksort?"

    User: "can you explain that part again?"
    ✓ Clarified as: "Can you explain how the partitioning in quicksort works?"

    Bad examples (DON'T DO THESE):
    User: "yes please"
    ✗ DON'T write: "I will explain the BST implementation"
    ✗ DON'T write: "Would you like to learn about BST implementation?"

    User: "what about space complexity?"
    ✗ DON'T write: "Let me explain the space complexity"
    ✗ DON'T write: "Would you like to know about space complexity?"

    Remember:
    - Keep user's perspective (write as if user is asking)
    - Maintain conversational tone
    - Add context from previous conversation
    - Question should be FROM user TO assistant

    If the question is already clear and specific, return needs_clarification=false.""",
        input_variables=["context", "question"]
    )
    
    chain = prompt | llm_with_clarification
    result = chain.invoke({
        "context": conversation_context,
        "question": current_question
    })
    
    if result.needs_clarification:
        print("---QUESTION NEEDS CLARIFICATION---")
        print(f"Original: {current_question}")
        print(f"Clarified: {result.clarified_question}")
        return {"messages": [HumanMessage(content=result.clarified_question)], "user_level": state["user_level"]}
    else:
        print("---NO CLARIFICATION NEEDED---")
        return {"messages": messages, "user_level": state["user_level"]}

### Nodes


def agent(state):
    """
    Invokes the agent model to generate a response based on the current state. Given
    the question, it will decide to retrieve using the retriever tool, or simply end.

    Args:
        state (messages): The current state

    Returns:
        dict: The updated state with the agent response appended to messages
    """
    print("---CALL AGENT---")
    messages = state["messages"]
    model = ChatOpenAI(model_name="gpt-4o-mini", temperature=0, streaming=True)
    model = model.bind_tools(tools)
    response = model.invoke(messages)
    # We return a list, because this will get added to the existing list
    return {"messages": [AIMessage(content=response.content)], "user_level": state["user_level"]}


def rewrite(state):
    """
    Transform the query to produce a better question.

    Args:
        state (messages): The current state

    Returns:
        dict: The updated state with re-phrased question
    """

    print("---TRANSFORM QUERY---")
    messages = state["messages"]
    question = messages[-1].content

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
    model = ChatOpenAI(model_name="gpt-4o-mini", temperature=0, streaming=True)
    response = model.invoke(msg)
    return {"messages": [AIMessage(content=response.content)], "user_level": state["user_level"]}


def generate(state):
    """
    Generate answer

    Args:
        state (messages): The current state

    Returns:
         dict: The updated state with re-phrased question
    """
    print("---GENERATE---")
    messages = state["messages"]
    question = messages[-1].content
    user_level = state["user_level"]  # Get user_level from state
    last_message = messages[-1]

    docs = last_message.content

    # Prompt
    prompt = PromptTemplate(
        template="""
    You are an assistant for question-answering tasks. Use the following pieces of retrieved context and answer the question based on user's level of competency.\n
    \n
    User Level: {user_level}\n
    Question: {question}\n
    Context: {context}\n
    \n
    TEACHING APPROACH:\n
    [beginner]\n
    - Use analogies (arrays as parking lots, stacks as plates)\n
    - Focus on fundamentals\n
    - Avoid complexity discussions\n
    - Break down step-by-step\n
    \n
    [intermediate]\n
    - Include implementation details\n
    - Basic complexity analysis\n
    - Compare approaches\n
    - Code examples when relevant\n

    [advanced]\n
    - Deep optimization discussion\n
    - Edge cases and tradeoffs\n
    - Advanced implementation details\n
    - System design considerations\n

    RULES:\n
    1. Strictly state if using general knowledge:\n
    "While the context doesn't cover this specifically, from my general knowledge..."\n

    2. Stay within user's level:\n
    - Beginner: No complexity, focus on intuition\n
    - Intermediate: Basic complexity, simple implementations\n
    - Advanced: Deep technical details, optimizations\n

    5. One concept at a time:\n
    "Let's focus on [concept] first. Would you like to explore [related concept] after?"\n
    \n
    """,
        input_variables=["context", "question","user_level"],
    )

    # LLM
    llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0, streaming=True)

    # Post-processing
    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    # Chain
    rag_chain = prompt | llm | StrOutputParser()

    # Run
    response = rag_chain.invoke({
        "context": docs, 
        "question": question,
        "user_level": user_level
    })
    return {"messages": [AIMessage(content=response)], "user_level": state["user_level"]}

from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import ToolNode

# Define a new graph
workflow = StateGraph(AgentState)

# Add all nodes
workflow.add_node("clarify", clarify_question)  # New clarification node
workflow.add_node("validate_topic", validate_dsa_question)
workflow.add_node("agent", agent)
retrieve = ToolNode([retriever_tool])
workflow.add_node("retrieve", retrieve)
workflow.add_node("rewrite", rewrite)  # Original rewrite for retrieval improvement
workflow.add_node("generate", generate)

# Start with clarification
workflow.add_edge(START, "clarify")

# Then validate if it's DSA-related
workflow.add_edge("clarify", "validate_topic")

# Add conditional edges from validation
workflow.add_conditional_edges(
    "validate_topic",
    lambda x: x["next"],
    {
        "proceed": "agent",
        "redirect": END
    }
)

# Decide whether to retrieve
workflow.add_conditional_edges(
    "agent",
    tools_condition,
    {
        "tools": "retrieve",
        END: END,
    },
)

# After retrieval, check document relevance
workflow.add_conditional_edges(
    "retrieve",
    grade_documents,
    {
        "generate": "generate",
        "rewrite": "rewrite"  # If docs aren't relevant, try rewriting for better retrieval
    }
)

# After rewriting for retrieval, try agent again
workflow.add_edge("rewrite", "agent")
workflow.add_edge("generate", END)

# Compile
from test_templates.memory import memory
graph = workflow.compile(memory)