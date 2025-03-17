from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import MessagesPlaceholder
from operator import itemgetter
from langchain_core.output_parsers import StrOutputParser

from model import llm_selected
from typing import Sequence
from langchain_core.messages import BaseMessage, RemoveMessage
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph, END

system_message = """You are a query analyzer for a DSA (Data Structures and Algorithms) chatbot. Your role is to determine whether a user query requires retrieving information from the knowledge base.

Return "true" if the query:
- Asks about DSA concepts, definitions, or implementations
- Requests technical details about algorithms or data structures
- Seeks explanation of time/space complexity
- Asks for code examples or implementation details

Return "false" if the query:
- Is a follow-up question relying on chat history
- Contains general acknowledgments or thanks
- Asks for clarification of previous responses
- Is a conversation flow message

Return ONLY "true" or "false" without any explanation."""

rc_prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        MessagesPlaceholder(variable_name="messages"),
    ])

llm = llm_selected

def get_rc_chain():
    return rc_prompt | llm

runnable = get_rc_chain()

class State(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]

workflow = StateGraph(state_schema=State)

def delete_messages(state):
    messages = state["messages"]
    if len(messages) > 3:
        return {"messages": [RemoveMessage(id=m.id) for m in messages[:-3]]}

def call_rc_model(state: State):   
    response = runnable.invoke(state)
    # Update message history with response:
    return {"messages": [response]}

workflow.add_edge(START, "model")
workflow.add_node("model", call_rc_model)
# workflow.add_edge("model", "delete_messages")
# workflow.add_node("delete_messages",delete_messages)

from test_templates.intial_template import memory

rc_app = workflow.compile(checkpointer=memory)