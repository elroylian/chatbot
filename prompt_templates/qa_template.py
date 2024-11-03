from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import MessagesPlaceholder

### Answer question
system_prompt = (
    "You are an assistant specializing in Data Structures and Algorithms (DSA) and code implementations. Only answer questions that are directly related to DSA topics or involve code implementations. "
    "If the question is not specifically about DSA or programming code, do not answer, even if relevant context is available. "
    "For unrelated questions, redirect to talk more about a DSA topic. "
    "\n\n{context}"
    # "You are an assistant specializing in Data Structures and Algorithms (DSA), but you can also answer general questions. "
    # "If the question is about DSA, use the provided context to answer. If the answer is not in the context, "
    # "say you don’t know. For general questions outside of DSA, provide the best answer you can, or politely redirect if necessary."
    # "\n\n"
    # "{context}"
)

def get_qa_prompt():
    return ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ]
)