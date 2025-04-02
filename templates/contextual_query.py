from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from operator import itemgetter
from langchain_core.output_parsers import StrOutputParser

from typing import Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from model import llm_selected

### Contextualize question ###
contextualize_q_system_prompt = (
"""You are a DSA question processor. Transform user's prompt into clear, context-aware queries.

OBJECTIVE: Rewrite user's prompt to include relevant context from chat history while maintaining original intent.

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

Return ONLY the reformulated question without explanation."""
)

contextualize_q_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", contextualize_q_system_prompt),
        MessagesPlaceholder("messages"),
    ]
)

llm = llm_selected

# Create contextual retrieval chain
def get_context_query_chain():
    return contextualize_q_prompt | llm 
 
runnable = get_context_query_chain()

class State(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
workflow = StateGraph(state_schema=State)
    
def call_contextual_model(state: State):   
    response = runnable.invoke(state)
    # Update message history with response:
    return {"messages": [response]}
 
workflow.add_edge(START, "model")
workflow.add_node("model", call_contextual_model)

from test_templates.intial_template import memory

contextual_app = workflow.compile(checkpointer=memory)

"""You are a DSA question processor. Transform user questions into clear, context-aware queries.

OBJECTIVE: Rewrite questions to include relevant context from chat history while maintaining original intent.

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

Prior Context: {chat_history}
Question: {input}

Return ONLY the reformulated question without explanation."""