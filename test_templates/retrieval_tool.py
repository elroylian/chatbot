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
# LLM still unsure how to respond to Thank you, Goodbye, etc. Hi, still okay i guess
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

def validate_dsa_question(state) -> dict[str, Any]:
    """Validates input to handle DSA questions, ensuring English-only interaction."""
    messages = state["messages"]
    question = messages[-1].content
    user_level = state["user_level"]
    
    class ValidationResult(BaseModel):
        message_type: str = Field(description="Type of message: 'dsa', 'pleasantry', 'non_english', or 'other'")
        response: str = Field(description="Response for non-DSA inputs")

    context_messages = messages[-6:-1] if len(messages) > 6 else messages[:-1]
    conversation_context = "\n".join([f"{'User: ' if isinstance(m, HumanMessage) else 'Assistant: '}{m.content}" for m in context_messages])
    
    prompt = PromptTemplate(
        template="""Analyze the input as a friendly DSA tutor:

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
    - Must be in English

    2. 'pleasantry' - Friendly conversation:
    - Greetings (hi, hello, hey)
    - Thanks/gratitude
    - Goodbyes
    - Emotional responses ("that makes sense", "I'm confused")
    - Small encouragements ("got it", "okay I understand")
    
    3. 'non_english' - Any non-English input:
    - Questions in other languages
    - Mixed language content
    - Non-English characters/scripts
    
    4. 'other' - Non-DSA technical content:
    - General programming
    - Math questions
    - Other CS topics
    - Non-technical questions

    For pleasantries: Respond naturally like a friendly tutor
    For non_english: Respond with English-only policy reminder
    For other: Redirect to DSA while being encouraging

    Return:
    1. message_type: 'dsa', 'pleasantry', 'non_english', or 'other'
    2. response: Appropriate response for non-DSA inputs""",
        input_variables=["context", "question"]
    )
    
    try:
        model = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.5, streaming=True, api_key=st.secrets["OpenAI_key"])
        chain = prompt | model.with_structured_output(ValidationResult)
        result = chain.invoke({"context": conversation_context, "question": question})
        
        if result.message_type == "dsa":
            return {"messages": messages, "user_level": user_level, "next": "proceed"}
        elif result.message_type == "non_english":
            return {
                "messages": [*messages, AIMessage(content="I can only communicate in English. Please rephrase your question in English.")],
                "user_level": user_level,
                "next": "redirect"
            }
        else:
            return {"messages": [*messages, AIMessage(content=result.response)], "user_level": user_level, "next": "redirect"}
            
    except Exception as e:
        print(f"Validation error: {str(e)}")
        return {"messages": messages, "user_level": user_level, "next": "proceed"}

def clarify_question(state):
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
# def agent(state):
#     """
#     Invokes the agent model to generate a response based on the current state. Given
#     the question, it will decide to retrieve using the retriever tool, or simply end.

#     Args:
#         state (messages): The current state

#     Returns:
#         dict: The updated state with the agent response appended to messages
#     """
#     print("---CALL AGENT---")
    
#     # Prompt
#     prompt = ChatMessagePromptTemplate
    
#     messages = state["messages"]
#     model = ChatOpenAI(temperature=0, model="gpt-4o-mini", streaming=True,api_key=st.secrets["OpenAI_key"])
#     model = model.bind_tools(tools)
#     response = model.invoke(messages)
#     # We return a list, because this will get added to the existing list
#     return {"messages": [response]}
def agent(state):
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

1. First, assess your confidence in providing a complete, accurate answer:
   - Consider if you need specific implementation details
   - Consider if you need exact complexity analysis
   - Consider if you need specific examples or edge cases

2. If your confidence is less than 90%%:
   - ALWAYS use the retrieve_documents tool
   - Base your answer on the retrieved information

3. If your confidence is 90%% or higher:
   - You may answer directly from your knowledge
   - Still use the tool if additional detail would be helpful

Remember: It's better to verify with the tool than risk providing incomplete or inaccurate information."""

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

def grade_documents(state) -> Literal["generate", "rewrite"]:
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
    """Generate response based on retrieved content and question"""
    print("\n=== DEBUG: GENERATE NODE ===")
    messages = state["messages"]
    print("Messages: ", state["messages"])
    
    # Find the last actual question by looking for the last HumanMessage
    # that triggered the retrieval flow
    question = None
    
    for msg in messages:
        if isinstance(msg, HumanMessage):
            question = msg.content
            
    if not question:
        return {
            "messages": [AIMessage(content="I couldn't properly process your question. Could you please rephrase it?")],
            "user_level": state["user_level"]
        }
        
    user_level = state["user_level"]
    docs = messages[-1].content  # Retrieved content is always last
    
    print(f"Generate received question: {question}")
    print(f"User level: {user_level}")
    # print(f"Docs length: {len(docs) if docs else 'None'}")
    
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
            template="""
                You are a DSA expert tutor. Adapt your teaching style to the user's level while maintaining technical accuracy.

                Current User Level: {user_level}

                [TEACHING APPROACHES]
                BEGINNER: Simple analogies, basic understanding, minimal jargon
                INTERMEDIATE: Basic complexity, implementation details, code examples
                ADVANCED: Deep optimization, system considerations, complex trade-offs

                • UNIVERSAL RULES:
                • Stay within DSA scope
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

                Question: {question}
                """)
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

# Add nodes
workflow.add_node("validate_topic", validate_dsa_question)
workflow.add_node("clarify", clarify_question)
workflow.add_node("agent", agent)
retrieve = ToolNode([retriever_tool])
workflow.add_node("retrieve", retrieve)
workflow.add_node("generate", generate)
workflow.add_node("rewrite", rewrite)

# Add edges
workflow.add_edge(START, "validate_topic")

# Modify validation to return three possible outcomes
workflow.add_conditional_edges(
    "validate_topic",
    lambda x: x["next"],
    {
        "proceed": "agent",
        "clarify": "clarify",
        "redirect": END
    }
)

# After clarification, go to agent
workflow.add_edge("clarify", "agent")

workflow.add_conditional_edges(
    "agent",
    tools_condition,
    {
        "tools": "retrieve",
        END: END,
    }
)

workflow.add_conditional_edges(
    "retrieve",
    grade_documents,
    {
        "generate": "generate",
        "rewrite": "rewrite",
    }
)

workflow.add_edge("generate", END)
workflow.add_edge("rewrite", "agent")

# Compile graph
from test_templates.memory import memory
graph = workflow.compile(memory)
