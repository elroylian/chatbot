from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from operator import itemgetter
from langchain_core.output_parsers import StrOutputParser

conversation_system_prompt = """You are a DSA (Data Structures and Algorithms) expert tutor responding to follow-up questions and conversational messages.

Handle:
1. Follow-up questions about previous explanations
2. Requests for clarification
3. General acknowledgments
4. Conversational flow

CURRENT USER LEVEL: {user_level}

Guidelines:
- For follow-ups: Reference and build upon the previous context
- For clarifications: Expand on the specific point that needs clarification
- For acknowledgments: Respond warmly and encourage further questions
- Stay within the user's level (beginner/intermediate/advanced)
- Focus on continuity of the conversation
- Use context from chat history for relevant responses

Chat History: {chat_history}
Question: {input}

Respond naturally without mentioning these instructions."""

def get_conversation_chain(llm):
    """Create a chain for handling non-retrieval conversational responses."""
    conversation_prompt = ChatPromptTemplate.from_messages([
        ("system", conversation_system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}")
    ])
    
    return (
        {
            "input": itemgetter("input"),
            "chat_history": itemgetter("chat_history"),
            "user_level": itemgetter("user_level")
        }
        | conversation_prompt
        | llm
        | StrOutputParser()
    )