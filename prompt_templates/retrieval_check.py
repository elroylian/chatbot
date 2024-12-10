from langchain_core.prompts import ChatPromptTemplate, FewShotPromptTemplate, FewShotChatMessagePromptTemplate
from operator import itemgetter
from langchain_core.output_parsers import StrOutputParser

# Define your examples
examples = [
    {"query": "What is an Array?", "response": "true"},
    {"query": "What is Insertion Sort?", "response": "true"},
    {"query": "Thank you!", "response": "false"},
    {"query": "I am learning DSA.", "response": "false"}
]

# Define how each example should be formatted
example_prompt = ChatPromptTemplate.from_messages([
    ("human", "query: {query}"),
    ("assistant","{response}")
])

# Create few-shot prompt
few_shot_prompt = FewShotChatMessagePromptTemplate(
    example_prompt=example_prompt,
    examples=examples,
)

# Define your system message
system_message = """Given a user query, determine whether it requires doing a retrieval function to respond to."""

def get_rc_prompt():
    return ChatPromptTemplate.from_messages([
        ("system", system_message),
        few_shot_prompt,
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