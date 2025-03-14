import csv
from test_templates.text_template import text_workflow
from langchain_core.messages import HumanMessage

# Read the CSV file
df = pd.read_csv('Book2.csv')

# Placeholder for chatbot and 4o-mini model invocation
# Define functions to get responses from the chatbot and 4o-mini model
def get_chatbot_response(question):
    # Implement the logic to get a response from your chatbot
    responses = []
    langgraph_config = {"configurable": {"thread_id": 1}}
    for i, q in enumerate(df['question']):
        prompt = q
        inputs = {
            "messages": [HumanMessage(prompt)],
            "user_level": "beginner"
        }

        current_graph = text_workflow.compile()
        
        try:
        
            output = current_graph.invoke(inputs, langgraph_config)
            response = output["messages"][-1].content
            responses.append(response)
        
        except Exception as e:
            responses.append("None")
        
    df["output1"] = responses
    df.to_csv('Output.csv', index=False)
    return "Chatbot response"

def get_4o_mini_response(question):
    # Implement the logic to get a response from the 4o-mini model
    return "4o-mini response"

# Iterate over questions and get responses
responses = []
for question in questions:
    chatbot_response = get_chatbot_response(question)
    mini_response = get_4o_mini_response(question)
    responses.append({'question': question, 'output1': chatbot_response, 'output2': mini_response})

# Print responses for verification
for response in responses:
    print(response) 