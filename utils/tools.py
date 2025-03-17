from db_connection import ChatDatabase
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.graph import MessagesState, START
from langgraph.prebuilt import ToolNode
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

db = ChatDatabase("chat.db")

@tool
def update_user_level_tool(user_id: str, new_level: str) -> str:
    """Parse the input string to extract user_id and new_level"""
    try: 
        result = db.safe_update_user_level(user_id, new_level)
        return "User level updated successfully." if result else "Failed to update user level."
    except Exception as e:
        return f"Error processing input: {str(e)}"

@tool
def get_user_level_tool(user_id: str) -> str:
    """Get user level for given user_id"""
    try:
        user_level = db.get_user_level(user_id.strip())
        return f"Current user level is {user_level}." if user_level else "User not found."
    except Exception as e:
        return f"Error retrieving user level: {str(e)}"

@tool
def analyze_user_progress(user_id: str) -> str:
    """Analyze user's learning progress and recent interactions"""
    try:
        # Get user's current level
        current_level = db.get_user_level(user_id)
        # Get recent chat history
        chat_history = db.load_chat_history(user_id, f"{user_id}_1")
        
        return f"Analysis for user {user_id}:\nCurrent Level: {current_level}\nInteractions: {len(chat_history)}"
    except Exception as e:
        return f"Error analyzing progress: {str(e)}"

# Update tools list
tools = [update_user_level_tool, get_user_level_tool, analyze_user_progress]
tool_node = ToolNode(tools)

# Set up the model

model = ChatOpenAI(model="gpt-4o-mini")
model = model.bind_tools(tools, parallel_tool_calls=False)


# Define nodes and conditional edges


# Define the function that determines whether to continue or not
def should_continue(state):
    messages = state["messages"]
    last_message = messages[-1]
    # If there is no function call, then we finish
    if not last_message.tool_calls:
        return "end"
    # Otherwise if there is, we continue
    else:
        return "continue"


# Define the function that calls the model
def call_model(state):
    messages = state["messages"]
    response = model.invoke(messages)
    # We return a list, because this will get added to the existing list
    return {"messages": [response]}


# Define a new graph
workflow = StateGraph(MessagesState)

# Define the two nodes we will cycle between
workflow.add_node("agent", call_model)
workflow.add_node("action", tool_node)

# Set the entrypoint as `agent`
# This means that this node is the first one called
workflow.add_edge(START, "agent")

# We now add a conditional edge
workflow.add_conditional_edges(
    # First, we define the start node. We use `agent`.
    # This means these are the edges taken after the `agent` node is called.
    "agent",
    # Next, we pass in the function that will determine which node is called next.
    should_continue,
    # Finally we pass in a mapping.
    # The keys are strings, and the values are other nodes.
    # END is a special node marking that the graph should finish.
    # What will happen is we will call `should_continue`, and then the output of that
    # will be matched against the keys in this mapping.
    # Based on which one it matches, that node will then be called.
    {
        # If `tools`, then we call the tool node.
        "continue": "action",
        # Otherwise we finish.
        "end": END,
    },
)

# We now add a normal edge from `tools` to `agent`.
# This means that after `tools` is called, `agent` node is called next.
workflow.add_edge("action", "agent")

# Set up memory
memory = MemorySaver()

# Finally, we compile it!
# This compiles it into a LangChain Runnable,
# meaning you can use it as you would any other runnable

# We add in `interrupt_before=["action"]`
# This will add a breakpoint before the `action` node is called
app = workflow.compile(checkpointer=memory)

# Process the user input
from analyser import graph

from langchain_core.messages import HumanMessage, AIMessage

config = {"configurable": {"thread_id": "1"}}
# input_message = HumanMessage(content="what is my user level, my id is 6fcf537a-8e1e-496b-be68-84841722fa57")
# for event in app.stream({"messages": [input_message]}, config, stream_mode="values"):
#     event["messages"][-1].pretty_print()

# Test the new tool
if __name__ == "__main__":
    chat_history = db.load_chat_history("6fcf537a-8e1e-496b-be68-84841722fa57", "6fcf537a-8e1e-496b-be68-84841722fa57_1")
    llm_chat_history = []
    # for message in chat_history:
    #                     if message["role"] == "user":
    #                         llm_chat_history.append(HumanMessage(content=message["content"]))
    #                     else:
    #                         llm_chat_history.append(AIMessage(content=message["content"]))
    conversation = [
    HumanMessage(content="What is an array?"),
    AIMessage(content="An array is a collection of elements stored in contiguous memory locations. Each element can be accessed using an index."),
    
    HumanMessage(content="How do I find the length of an array?"),
    AIMessage(content="In most programming languages, you can use a built-in function or property like `len(array)` in Python or `array.length` in JavaScript."),
    
    HumanMessage(content="What is a loop?"),
    AIMessage(content="A loop is a programming construct that repeats a block of code until a certain condition is met. Common types include `for` loops and `while` loops."),
    
    HumanMessage(content="Can you explain how to sort an array?"),
    AIMessage(content="Sure! You can use algorithms like Bubble Sort, which repeatedly swaps adjacent elements if they are in the wrong order. However, Bubble Sort is not efficient for large datasets."),
    
    HumanMessage(content="What is the time complexity of Bubble Sort?"),
    AIMessage(content="The time complexity of Bubble Sort is O(n^2), where n is the number of elements in the array. This makes it inefficient for large datasets."),
    
    HumanMessage(content="What is a stack?"),
    AIMessage(content="A stack is a linear data structure that follows the Last-In-First-Out (LIFO) principle. Elements are added and removed from the top of the stack."),
    
    HumanMessage(content="How do I implement a stack in Python?"),
    AIMessage(content="You can implement a stack using a list in Python. Use `append()` to push elements and `pop()` to remove elements from the top."),
    
    HumanMessage(content="What is a queue?"),
    AIMessage(content="A queue is a linear data structure that follows the First-In-First-Out (FIFO) principle. Elements are added at the rear and removed from the front."),
    
    HumanMessage(content="How do I implement a queue in Python?"),
    AIMessage(content="You can use the `collections.deque` class in Python to implement a queue. Use `append()` to enqueue and `popleft()` to dequeue.")
]
    graph.update_state(values = {"messages": conversation}, config = config)
    
    test_message = HumanMessage(content="Hi")
    for event in graph.stream({"messages": [test_message],"user_level": "Advanced"}, config, stream_mode="values"):
        event["messages"][-1].pretty_print()