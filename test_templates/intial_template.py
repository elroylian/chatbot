from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser

from typing import Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict
from langgraph.graph import START, MessagesState, StateGraph
from model import llm_selected

### Initial Question ###
inital_system_prompt = (    
"""You are a chat application specializing in Data Structures and Algorithms (DSA) and code implementations.

The user is new to your application and you need to ask the 3 following questions and use a scale of 1-5 to gauge:
- Familiarity with basic data structures (arrays, linked lists, stacks, queues)
- Understanding of sorting algorithms (e.g., insertion sort, merge sort)
- Experience with advanced topics (e.g., trees, graphs, dynamic programming)

Have a conversation with the user to get their inputs on the questions to gauge their competency level with DSA.

During each iteration, you are going to iteratively build the JSON object with the necessary information.

Once you have everything, thank the user, determine their competency level as 'beginner', 'intermediate', or 'advanced'.

Determine their competency level strictly based on the following criteria:
- Beginner: if most of the answers are 1-2
- Intermediate: if most of the answers are 3-4
- Advanced: if most of the answers are 5

After that you must prompt the user to ask their DSA question and use phrases like "What DSA question can I help you with today?" or "Please go ahead and ask your DSA question now.

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

llm = llm_selected
    
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

"""
You are a chat application specializing in Data Structures and Algorithms (DSA) and code implementations.

The user is new to your application and you need to ask the 3 following questions and use a scale of 1-5 to gauge:
- Familiarity with basic data structures (arrays, linked lists, stacks, queues)
- Understanding of sorting algorithms (e.g., insertion sort, merge sort)
- Experience with advanced topics (e.g., trees, graphs, dynamic programming)

Have a conversation with the user to get their inputs on the questions to gauge their competency level with DSA.

During each iteration, you are going to iteratively build the JSON object with the necessary information.

Once you have everything, thank the user, determine their competency level as 'beginner', 'intermediate', or 'advanced'.

Determine their competency level strictly based on the following criteria:
- Beginner: if most of the answers are 1-2
- Intermediate: if most of the answers are 3-4
- Advanced: if most of the answers are 5

After that you must prompt the user to ask their DSA question and use phrases like "What DSA question can I help you with today?" or "Please go ahead and ask your DSA question now.

OUTPUT FORMAT:
**ALL** text, including any explanations or clarifications, must be contained within the "message" field.
Each response MUST strictly always be a syntactically correct JSON with the following format:
{{
    "message": string,
    "data": {{
        "user_level": string | null
    }}
}}

You must ask a follow-up question if the user's input is invalid or incomplete.
    """