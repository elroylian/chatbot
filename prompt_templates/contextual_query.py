from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from operator import itemgetter
from langchain_core.output_parsers import StrOutputParser

### Contextualize question ###
contextualize_q_system_prompt = (
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