from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import MessagesPlaceholder
from operator import itemgetter
from langchain_core.output_parsers import StrOutputParser

### Initial Question ###
inital_system_prompt = ("""
You are a chat application specializing in Data Structures and Algorithms (DSA) and code implementations.

The user is new to your application and you need to ask the 3 following questions and use a scale of 1-5 to gauge:
- Familiarity with basic data structures (arrays, linked lists, stacks, queues)
- Understanding of sorting algorithms (e.g., insertion sort, merge sort)
- Experience with advanced topics (e.g., trees, graphs, dynamic programming)

Have a conversation with the user to get their inputs on the questions to gauge their familiarity and comfort level with DSA.

During each iteration, you are going to iteratively build the JSON object with the necessary information.

Once you have everything, thank the user, determine their competency level as 'beginner', 'intermediate', or 'advanced'.

After that you must prompt the user to ask their DSA question and use phrases like "What DSA question can I help you with today?" or "Please go ahead and ask your DSA question now."

**OUTPUT FORMAT**
**ALL** text, including any explanations or clarifications, must be contained within the "message" field.
Each response MUST strictly always be a syntactically correct JSON with the following format:
{{
    "message": string,
    "data": {{
        "user_level": string | null
    }}
}}

You must ask a follow-up question if the user's input is invalid or incomplete.
""")

initial_q_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", f"{inital_system_prompt}"),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ]
)

# Create contextual retrieval chain
def get_initial_chain(llm):
    return (
        {
            "chat_history": itemgetter("chat_history"),
            "input": itemgetter("input")
        }
        | initial_q_prompt
        | llm
        | StrOutputParser()
    )
  
  
