from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import MessagesPlaceholder
from operator import itemgetter
from langchain_core.output_parsers import StrOutputParser

### Contextualize question ###
contextualize_q_system_prompt = (
    "Given a chat history and the latest user question "
    "which might reference context in the chat history, "
    "formulate a standalone question which can be understood "
    "without the chat history. Do NOT answer the question, "
    "just reformulate it if needed and otherwise return it as is."
)

contextualize_q_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", contextualize_q_system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ]
)

# Create contextual retrieval chain
def get_context_query_chain(llm):
    return (
        {
            "chat_history": itemgetter("chat_history"),
            "input": itemgetter("input")
        }
        | contextualize_q_prompt
        | llm
        | StrOutputParser()
    )