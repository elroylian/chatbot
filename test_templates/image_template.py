from langchain.tools import Tool
from typing import Annotated, Literal, Sequence
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from langgraph.graph import END, StateGraph, START
from operator import itemgetter

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_level: str

def generate_dsa_response(state):
    """Generate a response using GPT-4o-mini's image understanding capabilities"""
    print("---GENERATING DSA RESPONSE---")
    messages = state["messages"]
    user_level = state["user_level"]
    
    # Format system message to guide the model
    system_msg = f"""You are explaining Data Structures and Algorithms concepts based on the provided image.
    The user's level is: {user_level}
    
    IMPORTANT: Always start by directly acknowledging what you see in the image. For example:
    - If asked "can you see the image?", respond with "Yes, I can see the image. It shows [describe what you see]..."
    - If asked about specific elements, point them out directly from the image
    - Reference specific visual elements when explaining concepts
    
    Adjust your explanation based on their level:
    - Beginner: Focus on fundamentals and intuitive explanations
    - Intermediate: Include implementation details and basic complexity
    - Advanced: Cover optimizations and advanced concepts
    
    Focus on explaining:
    1. The data structure or algorithm shown in the image
    2. The key components and relationships visible
    3. Any operations or processes being demonstrated
    4. Common use cases and advantages
    
    Always maintain context about what you're actually seeing in the image rather than giving generic responses.
    """
    
    # Initialize model
    model = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)
    
    # Create full message list with system prompt
    full_messages = [
        HumanMessage(content=system_msg),
        messages[-1]  # The message containing image and user query
    ]
    
    # Get response
    response = model.invoke(full_messages)
    
    return {"messages": [AIMessage(content=response.content)], "user_level": user_level}

# Define workflow
workflow = StateGraph(AgentState)

# Add node
workflow.add_node("generate_response", generate_dsa_response)

# Add edges
workflow.add_edge(START, "generate_response")
workflow.add_edge("generate_response", END)

# Compile
from test_templates.memory import memory
graph = workflow.compile(memory)

def get_image_chain(llm):
    """Create an image analysis chain"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are analyzing and explaining DSA concepts from images.
        Adjust your explanation for the user's level: {user_level}
        
        Explain:
        1. The data structure/algorithm shown
        2. Key components and relationships
        3. Operations and processes demonstrated
        4. Practical applications
        """),
        ("human", "{human_msg}")
    ])
    
    return (
        {
            "human_msg": itemgetter("human_msg"),
            "user_level": itemgetter("user_level")
        }
        | prompt
        | llm
        | StrOutputParser()
    )