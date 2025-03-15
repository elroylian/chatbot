import pandas as pd
from langchain_core.messages import HumanMessage
from test_templates.text_template import text_workflow
import time
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
import streamlit as st

# Configure a memory object if needed
# from test_templates.memory import memory

# Read the CSV file
df = pd.read_csv('Book2.csv')

# Create output columns
df['chatbot_response'] = None
df['gpt4o_mini_response'] = None

# Initialize GPT-4o-mini model
def get_gpt4o_mini():
    return ChatOpenAI(
        model_name="gpt-4o-mini",
        temperature=0,
        api_key=st.secrets["OpenAI_key"]
    )

# Process each question
langgraph_config = {"configurable": {"thread_id": "evaluation_test"}}
memory = MemorySaver()
current_graph = text_workflow.compile(memory)


for index, row in df.iterrows():
    question = row['question']
    print(f"Processing question {index+1}/{len(df)}: {question[:50]}...")
    
    # Get chatbot response
    try:
        inputs = {
            "messages": [HumanMessage(content=question)],
            "user_level": "beginner"  # Assuming beginner level for testing
        }
        
          # Compile the graph for each question
        output = current_graph.invoke(inputs, langgraph_config)
        chatbot_response = output["messages"][-1].content
        df.at[index, 'chatbot_response'] = chatbot_response
    except Exception as e:
        print(f"Error with chatbot response: {str(e)}")
        df.at[index, 'chatbot_response'] = f"ERROR: {str(e)}"
    
    # Get GPT-4o-mini response
    try:
        gpt4o = get_gpt4o_mini()
        mini_response = gpt4o.invoke(question).content
        df.at[index, 'gpt4o_mini_response'] = mini_response
    except Exception as e:
        print(f"Error with GPT-4o-mini response: {str(e)}")
        df.at[index, 'gpt4o_mini_response'] = f"ERROR: {str(e)}"
    
    # Save intermediate results in case of interruption
    if index % 5 == 0:
        df.to_csv('evaluation_results.csv', index=False)
        print(f"Saved progress at question {index+1}")
    
    # Add a small delay to avoid rate limiting
    time.sleep(1)

# Save final results
df.to_csv('evaluation_results.csv', index=False)
print("Evaluation complete. Results saved to evaluation_results.csv")