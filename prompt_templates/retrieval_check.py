from langchain_core.prompts import ChatPromptTemplate
from operator import itemgetter
from langchain_core.output_parsers import StrOutputParser

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

def get_rc_prompt():
    return ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("human", "{input}")
    ])

def get_rc_chain(llm):
    return (
        {
            "input": itemgetter("input")
        }
        | get_rc_prompt()
        | llm
        | StrOutputParser()
    )