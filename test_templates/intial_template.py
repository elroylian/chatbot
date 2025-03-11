from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser

from typing import Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict
from langgraph.graph import START, MessagesState, StateGraph
from utils.model import get_llm

### Initial Question ###
inital_system_prompt = (    
"""You are a chat application specializing in Data Structures and Algorithms (DSA) and code implementations.

The user is new to your application and you need to assess their DSA knowledge level. Ask ONE question at a time in this specific order:

1. First, ask about their familiarity with basic data structures (arrays, linked lists, stacks, queues) on a scale of 1-5.

2. Only if they rate basic structures 2 or higher, ask about their understanding of sorting algorithms (e.g., insertion sort, merge sort) on a scale of 1-5.
   If they rated basic structures as 1, automatically assign 1 to sorting algorithms.

3. Only if they rate sorting algorithms 2 or higher, ask about their experience with advanced topics (e.g., trees, graphs, dynamic programming) on a scale of 1-5.
   If they rated sorting algorithms as 1, automatically assign 1 to advanced topics.

Determine their competency level strictly based on the following criteria:
- Beginner: if most of the answers are 1-2
- Intermediate: if most of the answers are 3-4
- Advanced: if most of the answers are 5

After completing the assessment, thank the user and prompt them to ask their DSA question using phrases like "What DSA question can I help you with today?" or "Please go ahead and ask your DSA question now."

OUTPUT FORMAT:
**ALL** text, including any explanations or clarifications, must be contained within the "message" field.
Each response MUST strictly always be a syntactically correct JSON with the following format:
{{
    "message": string,
    "data": {{
        "user_level": string | null
    }}
}}

You must ask a follow-up question if the user's input is invalid or incomplete."""
)

initial_q_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", f"{inital_system_prompt}"),
        MessagesPlaceholder(variable_name="messages"),
    ]
)

llm = get_llm()
    
def get_initial_chain():
    return initial_q_prompt | llm

runnable = get_initial_chain()

class State(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]

workflow = StateGraph(state_schema=State)


def call_initial_model(state: State):   
    response = runnable.invoke(state)
    # Update message history with response:
    return {"messages": [response]}

workflow.add_edge(START, "model")
workflow.add_node("model", call_initial_model)

from test_templates.memory import memory

app = workflow.compile(checkpointer=memory)