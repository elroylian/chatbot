from langchain.tools.retriever import create_retriever_tool
from utils.chunk_doc import get_retriever
import os
import streamlit as st
from langchain import hub
from typing import Annotated, Literal, Sequence, Any, Dict
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langgraph.prebuilt import tools_condition
from langgraph.graph.message import add_messages
from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import ToolNode
from model import llm_selected

# TODO
# LLM still unsure how to respond to Thank you, Goodbye, etc. Hi, still okay i guess
# Keep testing!

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

def validate_dsa_question(state) -> dict[str, Any]:
    """
    Determines whether the question is DSA-related, with improved handling of
    context-dependent questions and greetings.
    
    Args:
        state: Current state containing messages and user_level
        
    Returns:
        dict[str, Any]: Dictionary containing:
            - messages: List of conversation messages
            - user_level: User's current level
            - next: Literal["proceed", "redirect"] indicating next action
    """
    messages = state["messages"]
    question = messages[-1].content
    user_level = state["user_level"]
    
    class ValidationResult(BaseModel):
        is_dsa: str = Field(description="Binary 'yes' or 'no' for DSA relevance")
        is_greeting: bool = Field(description="Whether the input is a greeting")
        redirect_message: str = Field(
            description="Friendly respond that they cannot answer the question and redirect to DSA topics if needed",
            # default="I'd be happy to help you learn about data structures and algorithms. What DSA topic would you like to explore?"
        )
        greeting_response: str = Field(
            description="Friendly greeting response if input is a greeting",
            default="Hello! I'm your DSA learning assistant. I'd be happy to help you learn about data structures and algorithms. What topic would you like to explore?"
        )

    # Get context from previous messages if they exist
    context_messages = messages[-6:-1] if len(messages) > 6 else messages[:-1]
    conversation_context = "\n".join([
        f"{'User: ' if isinstance(m, HumanMessage) else 'Assistant: '}{m.content}"
        for m in context_messages
    ])
    
    prompt = PromptTemplate(
        template="""Analyze if this question is DSA-related or a greeting:

Previous conversation:
{context}

Current input: {question}

First check if the input is a greeting:
- Common greetings: hi, hello, hey, good morning/afternoon/evening
- Variations like "hi there", "hello!", etc.
- If it's a greeting, set is_greeting=true and provide a friendly greeting_response

If not a greeting, check if it's DSA-related:
- Direct questions about DSA concepts
- Follow-up questions about algorithms/data structures
- Questions about implementation or complexity

Return:
1. is_dsa: "yes" for DSA questions, "no" otherwise
2. is_greeting: true for greetings, false otherwise
3. greeting_response: friendly greeting if applicable
4. redirect_message: friendly suggestion for non-DSA questions""",
        input_variables=["context", "question"]
    )
    
    try:
        model = ChatOpenAI(
            model_name="gpt-4o-mini", 
            temperature=0, 
            streaming=True, 
            api_key=st.secrets["OpenAI_key"]
        )
        chain = prompt | model.with_structured_output(ValidationResult)
        result = chain.invoke({
            "context": conversation_context,
            "question": question
        })
        
        # Handle greetings first
        if result.is_greeting:
            return {
                "messages": [*messages, AIMessage(content=result.greeting_response)],
                "user_level": user_level,
                "next": "redirect"  # End after greeting response
            }
        
        # Handle DSA vs non-DSA questions
        return {
            "messages": messages if result.is_dsa.lower() == "yes" else [*messages, AIMessage(content=result.redirect_message)],
            "user_level": user_level,
            "next": "proceed" if result.is_dsa.lower() == "yes" else "redirect"
        }
            
    except Exception as e:
        print(f"Validation error: {str(e)}")
        # On error, proceed with original message
        return {
            "messages": messages,
            "user_level": user_level,
            "next": "proceed"
        }

def clarify_question(state):
    """
    Clarifies ambiguous questions by maintaining conversation context,
    with improved handling of pronoun references to DSA concepts.
    """
    print("\n=== DEBUG: CLARIFY NODE ===")
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
        needs_clarification: bool = Field(
            description="Set to true if the question contains pronouns or implicit references to previously discussed DSA concepts"
        )
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


# def agent(state):
#     """
#     Enhanced agent function with correct retrieval method
#     """
#     print("\n=== DEBUG: AGENT NODE ===")
#     messages = state["messages"]
#     question = messages[-1].content
#     print(f"Question received by agent: {question}")
    
#     try:
#         # Create system message to enforce proper tool usage and response format
#         system_message = """You are a DSA expert assistant. Follow these steps for EVERY question:
#         1. ALWAYS use the retrieve_documents tool first to get information
#         2. Wait for the tool's response
#         3. Synthesize the retrieved information into a clear explanation
#         4. If the retrieved information is insufficient, clearly state that and provide a general explanation
        
#         IMPORTANT: 
#         - Always complete the full retrieval and response process
#         - Never return just a message about needing to retrieve information
#         - Provide complete, informative responses
#         """
        
#         # Prepare messages with system instruction
#         full_messages = [
#             HumanMessage(content=system_message),
#             *messages
#         ]
        
#         # Initialize model with tools and strict temperature
#         model = ChatOpenAI(
#             model_name="gpt-4o-mini", 
#             temperature=0, 
#             streaming=True, 
#             api_key=st.secrets["OpenAI_key"]
#         )
#         model_with_tools = model.bind_tools(tools)
        
#         # Create a specific prompt to force tool usage
#         tool_prompt = HumanMessage(content=f"""Please provide information about: {question}
#         Remember to:
#         1. Use the retrieve_documents tool first
#         2. Process the retrieved information
#         3. Provide a complete response""")
        
#         # Get response with explicit tool usage
#         response = model_with_tools.invoke([*full_messages, tool_prompt])
        
#         # Validate response
#         if not response.content.strip() or "need to retrieve" in response.content.lower():
#             print("Warning: Invalid response detected, forcing retrieval")
#             # Force direct retrieval as fallback
#             docs = retriever.invoke(question)
#             if docs:
#                 # Process the retrieved documents
#                 context = "\n".join(doc.page_content for doc in docs)
                
#                 # Generate response with retrieved context
#                 prompt = PromptTemplate(
#                     template="""Based on the following information, provide a complete explanation about {question}.
                    
#                     Retrieved information:
#                     {context}
                    
#                     If the retrieved information is insufficient, provide a general explanation based on your knowledge
#                     but clearly state that you're doing so.
#                     """,
#                     input_variables=["question", "context"]
#                 )
                
#                 chain = prompt | model | StrOutputParser()
#                 response_content = chain.invoke({
#                     "question": question,
#                     "context": context
#                 })
#             else:
#                 response_content = "I apologize, but I couldn't find specific information about that. Let me provide a general explanation based on my knowledge."
#         else:
#             response_content = response.content
            
#         print(f"Final response length: {len(response_content)}")
#         return {"messages": [AIMessage(content=response_content)], "user_level": state["user_level"]}
        
#     except Exception as e:
#         print(f"Error in agent: {str(e)}")
#         # Fallback to direct explanation
#         try:
#             print("Attempting fallback retrieval...")
#             docs = retriever.invoke(question)
#             if docs:
#                 context = "\n".join(doc.page_content for doc in docs)
#                 return {
#                     "messages": [AIMessage(content=f"Here's what I found about {question}: {context}")],
#                     "user_level": state["user_level"]
#                 }
#             else:
#                 return {
#                     "messages": [AIMessage(content=f"I apologize, but I encountered an issue retrieving specific information about {question}. Please try rephrasing your question.")],
#                     "user_level": state["user_level"]
#                 }
#         except Exception as e2:
#             print(f"Fallback retrieval failed: {str(e2)}")
#             return {
#                 "messages": [AIMessage(content="I encountered an error processing your question. Please try asking in a different way.")],
#                 "user_level": state["user_level"]
#             }

# def rewrite(state):
#     """Debug version of rewrite with validation"""
#     print("\n=== DEBUG: REWRITE NODE ===")
#     messages = state["messages"]
#     question = messages[-1].content
#     print(f"Rewriting question: {question}")

#     try:
#         msg = [
#             HumanMessage(
#                 content="""Improve this question to be more specific and searchable:
#                 Question: {question}
#                 Make it clearly about DSA concepts.""".format(question=question)
#             )
#         ]

#         model = ChatOpenAI(model_name="gpt-4o-mini", temperature=0, streaming=True, api_key=st.secrets["OpenAI_key"])
#         response = model.invoke(msg)
#         print(f"Rewritten as: {response.content}")
#         return {"messages": [AIMessage(content=response.content)], "user_level": state["user_level"]}
#     except Exception as e:
#         print(f"Error in rewrite: {str(e)}")
#         return {"messages": [HumanMessage(content=question)], "user_level": state["user_level"]}

# def grade_documents(state) -> Literal["generate", "rewrite"]:
#     """Debug version of grading with content validation"""
#     print("\n=== DEBUG: GRADE DOCUMENTS ===")
    
#     messages = state["messages"]
#     last_message = messages[-1]
#     question = messages[0].content
#     docs = last_message.content
    
#     print(f"Grading question: {question}")
#     print(f"Documents content length: {len(docs) if docs else 'None'}")
    
#     # Basic content validation
#     if not docs or len(docs.strip()) < 10:
#         print("---NO VALID DOCS TO GRADE---")
#         return "rewrite"
        
#     try:
#         class grade(BaseModel):
#             binary_score: str = Field(description="Relevance score 'yes' or 'no'")
            
#         model = ChatOpenAI(model_name="gpt-4o-mini", temperature=0, streaming=True, api_key=st.secrets["OpenAI_key"])
#         llm_with_tool = model.with_structured_output(grade)
        
#         prompt = PromptTemplate(
#             template="""Grade if this content is relevant to the question.
#             Question: {question}
#             Content: {context}
#             Give 'yes' if there's ANY relevant information about the topic.""",
#             input_variables=["context", "question"],
#         )
        
#         chain = prompt | llm_with_tool
#         result = chain.invoke({"question": question, "context": docs})
#         print(f"Grade result: {result.binary_score}")
        
#         return "generate" if result.binary_score.lower() == "yes" else "rewrite"
        
#     except Exception as e:
#         print(f"Error in grading: {str(e)}")
#         return "generate" if docs else "rewrite"


################################################################################################################
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
    model = ChatOpenAI(temperature=0, model="gpt-4o-mini", streaming=True,api_key=st.secrets["OpenAI_key"])
    model = model.bind_tools(tools)
    response = model.invoke(messages)
    # We return a list, because this will get added to the existing list
    return {"messages": [response]}

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
    model = ChatOpenAI(temperature=0, model="gpt-4o-mini", streaming=True,api_key=st.secrets["OpenAI_key"])

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

def generate(state):
    """Debug version of generate with content validation"""
    print("\n=== DEBUG: GENERATE NODE ===")
    messages = state["messages"]
    question = messages[-1].content
    user_level = state["user_level"]
    docs = messages[-1].content
    
    print(f"Generate received question: {question}")
    print(f"User level: {user_level}")
    print(f"Docs length: {len(docs) if docs else 'None'}")
    
    if not docs or len(docs.strip()) < 10:
        print("---NO CONTENT TO GENERATE FROM---")
        return {"messages": [AIMessage(content="I apologize, but I couldn't find relevant information to answer your question. Please try rephrasing it.")], "user_level": state["user_level"]}
        
    try:
        llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0, streaming=True, api_key=st.secrets["OpenAI_key"])
        
        # prompt = PromptTemplate(
        #     template="""Answer based on the following context. If context is insufficient, say so clearly.
        #     Question: {question}
        #     User Level: {user_level}
        #     Context: {context}
            
        #     If you don't find specific information about the topic, you can provide a general explanation based on your knowledge, but clearly state that you're doing so.""",
        #     input_variables=["context", "question", "user_level"],
        # )
        prompt = PromptTemplate(
            input_variables=['context', 'question','user_level'], 
            input_types={}, 
            partial_variables={}, 
            template="""You are a DSA expert tutor. Adapt your teaching style to the user's level while maintaining technical accuracy.

Current User Level: {user_level}

• BEGINNER LEVEL APPROACH:
  • Use simple analogies and metaphors
    • Compare arrays to parking lots
    • Explain stacks like plates in a cafeteria
    • Describe trees as family trees
  • Focus on basic understanding
    • Avoid complexity discussions
    • Use step-by-step explanations
    • Provide visual examples when possible
  • Keep language simple
    • Minimize technical jargon
    • Use everyday examples
    • Explain concepts interactively

• INTERMEDIATE LEVEL APPROACH:
  • Technical content focus
    • Include basic time/space complexity
    • Show implementation details
    • Provide code examples
  • Teaching methods
    • Compare different approaches
    • Explain basic trade-offs
    • Connect related concepts
  • Code implementation
    • Show practical examples
    • Discuss common patterns
    • Address basic optimizations

• ADVANCED LEVEL APPROACH:
  • Technical depth
    • Deep optimization discussions
    • Thorough edge case analysis
    • Performance considerations
  • System considerations
    • Memory/cache implications
    • Concurrency aspects
    • Scalability factors
  • Implementation focus
    • Advanced optimization techniques
    • System design impacts
    • Complex trade-offs

• UNIVERSAL RULES:
  • Stay within DSA scope
    • Redirect non-DSA questions politely
    • Focus on one concept at a time
    • Offer to explore related topics after
  • Use context appropriately
    • Start with provided context: "{context}"
    • Clearly indicate when using general knowledge
    • Stay within user's competency level
  • Maintain level-appropriate depth
    • Match technical depth to user level
    • Scale example complexity appropriately
    • Use suitable terminology

Question: {question}""")
        # prompt = hub.pull("rlm/rag-prompt")
        
        chain = prompt | llm | StrOutputParser()
        response = chain.invoke({
            "context": docs,
            "question": question,
            "user_level": user_level
        })
        
        print(f"Generated response length: {len(response)}")
        return {"messages": [AIMessage(content=response)], "user_level": state["user_level"]}
        
    except Exception as e:
        print(f"Error in generate: {str(e)}")
        return {"messages": [AIMessage(content="I encountered an error generating a response. Please try asking your question again.")], "user_level": state["user_level"]}

################################################################################################################
# Graph setup
workflow = StateGraph(AgentState)

# Add nodes - remove the rewrite node
workflow.add_node("clarify", clarify_question)
workflow.add_node("validate_topic", validate_dsa_question)
workflow.add_node("agent", agent)
retrieve = ToolNode([retriever_tool])
workflow.add_node("retrieve", retrieve)
workflow.add_node("generate", generate)
workflow.add_node("rewrite", rewrite)  # Re-writing the question

# Add edges
workflow.add_edge(START, "clarify")
workflow.add_edge("clarify", "validate_topic")

workflow.add_conditional_edges(
    "validate_topic",
    lambda x: x["next"],
    {
        "proceed": "agent",
        "redirect": END
    }
)

workflow.add_conditional_edges(
    "agent",
    tools_condition,
    {
        "tools": "retrieve",
        END: END,
    }
)

# workflow.add_conditional_edges(
#     "retrieve",
#     grade_documents,
    
#     {
#         "generate": "generate",
#         "rewrite": "agent"  # Changed from "rewrite" to "agent"
#     }
# )
workflow.add_conditional_edges(
    "retrieve",
    grade_documents,
)

workflow.add_edge("generate", END)
workflow.add_edge("rewrite", "agent")

# Compile graph
from test_templates.memory import memory
graph = workflow.compile(memory)
