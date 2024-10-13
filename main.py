# Import necessary libraries
from langchain_community.llms import Ollama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.example_selectors.base import BaseExampleSelector
from langchain.chains import LLMChain
import getpass
import os

# Initialize the LLM
# llm = Ollama(model="gemma2:2b", base_url="http://localhost:11434")
llm = Ollama(model="llama3.2", base_url="http://localhost:11434")

# Create the prompt template to explain concepts
concept_prompt = ChatPromptTemplate.from_template(
    "You are a friendly and approachable Data Structures and Algorithms Expert. "
    "Explain the concept below in simple bullet points that are easy to understand, "
    "and follow up with a related question to engage the user: {concept}"
)

# Create the prompt template for a dynamic greeting
greeting_prompt = PromptTemplate.from_template(
    "You are a friendly assistant who specializes in Data Structures and Algorithms. The user has greeted you. "
    "Respond with a warm and dynamic greeting, and mention that you are here to help with any Data Structures and Algorithms questions they have."
)

test_prompt = PromptTemplate.from_template(
    "Determine whether the input below is a greeting, a question about Data Structures and Algorithms, a general statement, or a greeting followed by a question. "
    "If it is only a greeting, return 'greeting'. If it is a concept-related question or a greeting followed by a question, return 'concept'. "
    "If it is a general conversational statement or comment that is not directly a question about Data Structures or a greeting, return 'general'. "
    "If the input is unclear or cannot be categorized, return 'unclear'. "
    "Consider that the input may contain typos or minor variations, but still classify it based on intent.\n"
    "Strictly only return 'greeting', 'concept', 'general', or 'unclear'.\n"
    "For example:\n"
    "1. Input: 'hello'\nOutput: 'greeting'\n"
    "2. Input: 'helo'\nOutput: 'greeting'\n"
    "3. Input: 'hi, how are you?'\nOutput: 'greeting'\n"
    "4. Input: 'can you explain recursion?'\nOutput: 'concept'\n"
    "5. Input: 'hey, tell me about linked lists'\nOutput: 'concept'\n"
    "6. Input: 'helo chat bot what is an array?'\nOutput: 'concept'\n"
    "7. Input: 'hello, what is an AVL tree?'\nOutput: 'concept'\n"
    "8. Input: 'so you are able to read my typo'\nOutput: 'general'\n"
    "9. Return only 'greeting', 'concept', 'general', or 'unclear'.\n"
    "Input: {user_input}"
)



# Function to generate a dynamic greeting
def generate_greeting():
    try:
        greeting_response = llm.invoke(greeting_prompt.format())
        return greeting_response
    except Exception as e:
        return f"Error: {e}"

# Function to classify user input using the custom example selector
def classify_input(user_input):
    try:
        formatted_prompt = test_prompt.format(user_input=user_input)
        classification = llm.invoke(formatted_prompt).strip().lower()

        # Remove any extra single or double quotes from the classification output
        classification = classification.replace("'", "").replace('"', "")

        # Debugging: Print classification to verify output
        print(f"Classification: '{classification}'")
        return classification
    except Exception as e:
            return f"Error: {e}"

# Function to handle user input
def insert_input(user_input):
    # Classify the input as either a greeting, concept, general statement, or unclear
    # formatted_prompt = test_prompt.format(user_input=user_input)
    # classification = llm.invoke(formatted_prompt).strip().lower()
    return llm.invoke(user_input)

    # # Remove any extra single or double quotes from the classification output
    # classification = classification.replace("'", "").replace('"', "")

    # # Debugging: Print classification to verify output
    # print(f"Classification: '{classification}'")

    # if classification == "greeting":
    #     print("Classified as a greeting")
    #     return generate_greeting()
    # elif classification == "concept":
    #     print("Classified as a concept query")
    #     try:
    #         formatted_prompt = concept_prompt.format(concept=user_input)
    #         response = llm.invoke(formatted_prompt)
    #         return response
    #     except Exception as e:
    #         return f"Error: {e}"
    # elif classification == "general":
    #     print("Classified as a general statement")
    #     return "Thank you for your comment. I'm here to assist you with any questions related to Data Structures and Algorithms. Let me know if you have anything specific you'd like to explore."
    # else:
    #     print("Classified as unclear")
    #     return "I'm here to help with Data Structures and Algorithms! Could you please specify what you'd like me to explain?"




# Main execution for testing purposes
if __name__ == "__main__":
    user_input = ""
    while user_input.lower() != "bye":
        user_input = input("Enter your query: ")
        if user_input.lower() == "bye":
            print("Goodbye!")
            break
        response = insert_input(user_input)
        print(response)
