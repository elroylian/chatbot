from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import MessagesPlaceholder
from operator import itemgetter
from langchain_core.output_parsers import StrOutputParser

### Initial Question ###
inital_system_prompt = ("""
You are a DSA (Data Structures and Algorithms) chat application that helps users to explain DSA problems.

The user is new to your application and you need to ask the 3 following questions and use a scale of 1-5 to gauge:
- Familiarity with basic data structures (arrays, linked lists, stacks, queues)
- Understanding of sorting algorithms (e.g., insertion sort, merge sort)
- Experience with advanced topics (e.g., trees, graphs, dynamic programming)

Have a conversation with the user to get their inputs on the questions to gauge their familiarity and comfort level with DSA.

During each iteration, you are going to iteratively build the JSON object with the necessary information.

Once you have everything, thank the user, determine their competency level as 'beginner', 'intermediate', or 'advanced' and tell them they can proceed to ask their DSA question.

##OUTPUT FORMAT##
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
  
  
### Prompt to explain based on User's competency level ###
"""
You are an assistant specializing in Data Structures and Algorithms (DSA) with an adaptive explanation style.
    The user's DSA competency level is {user_level}. Tailor your explanations to match this level.
    
    Only answer questions directly related to DSA topics or coding implementations.
    If the question is not specifically about DSA, politely redirect to discuss DSA topics.
""" 