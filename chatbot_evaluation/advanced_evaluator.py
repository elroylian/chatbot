import pandas as pd
from langchain_core.messages import HumanMessage, SystemMessage
import time
from langchain_openai import ChatOpenAI
from langchain_deepseek import ChatDeepSeek
import os
import json
import re

# Configure DeepSeek API key
if not os.getenv("DEEPSEEK_API_KEY"):
    # Use your preferred method to get the API key
    import streamlit as st
    os.environ["DEEPSEEK_API_KEY"] = st.secrets["DEEPSEEK_API_KEY"]

# Read the results CSV file with both model outputs
df = pd.read_csv('chatbot_res_adv.csv')

# Add grading columns
df['grading_score'] = None
df['grading_feedback'] = None
df['winner'] = None

# Initialize DeepSeek model
def get_deepseek_grader():
    return ChatDeepSeek(
        model="deepseek-reasoner",  # Using reasoner for better evaluation capabilities
        temperature=0,
        max_tokens=None,
        timeout=None
    )

# Create grading rubric with emphasis on advanced-appropriate content
advanced_grading_system_prompt = """You are an expert evaluator of Data Structures and Algorithms (DSA) educational content SPECIFICALLY DESIGNED FOR ADVANCED-LEVEL learners.

Your task is to compare and grade responses to DSA questions from two different AI assistants, keeping in mind that the target audience consists of ADVANCED-LEVEL learners who already understand fundamental and intermediate concepts but need expert-level insights, optimizations, and theoretical depth.

Grading criteria tailored for advanced-level content:
1. Technical Sophistication (0-5): Deep technical accuracy with nuanced explanations of complex algorithmic behaviors, edge cases, and theoretical foundations.
2. Optimization Insight (0-5): Detailed analysis of performance optimization opportunities, algorithmic refinements, and implementation efficiency.
3. Complexity Analysis (0-5): Rigorous time and space complexity analysis including amortized analysis, mathematical proofs, and performance guarantees.
4. System-level Integration (0-5): Discussion of how algorithms and data structures interact with broader systems, including distributed contexts, memory hierarchies, and hardware considerations.
5. Research Connections (0-5): References to current research, advanced variations, and cutting-edge applications of classic algorithms and data structures.

When evaluating, prioritize these advanced-focused factors:
- Provides sophisticated technical insights beyond standard textbook explanations
- Discusses non-trivial optimizations and implementation nuances
- Analyzes algorithmic behavior under various conditions and constraints
- Makes connections to theoretical computer science and mathematical foundations
- Addresses real-world, large-scale, or specialized applications of the concepts

For each response, provide:
1. Individual scores for each criterion
2. A total score out of 25
3. 2-3 specific strengths of the response for advanced learners
4. 1-2 areas for improvement to better serve advanced learners
5. Your determination of which response is better overall for ADVANCED users

Format your response as a JSON object with the following structure:
{
  "model1_score": {
    "technical_sophistication": 0-5,
    "optimization_insight": 0-5,
    "complexity_analysis": 0-5,
    "system_level_integration": 0-5,
    "research_connections": 0-5,
    "total": 0-25
  },
  "model2_score": {
    "technical_sophistication": 0-5,
    "optimization_insight": 0-5,
    "complexity_analysis": 0-5,
    "system_level_integration": 0-5,
    "research_connections": 0-5,
    "total": 0-25
  },
  "model1_strengths": ["strength1", "strength2", ...],
  "model1_improvements": ["improvement1", "improvement2", ...],
  "model2_strengths": ["strength1", "strength2", ...],
  "model2_improvements": ["improvement1", "improvement2", ...],
  "winner": "model1" or "model2" or "tie",
  "reasoning": "Brief explanation of why one response is better for ADVANCED users"
}

The JSON structure must be exact - do not include any additional text before or after the JSON.
IMPORTANT: Your response must ONLY be valid JSON. Do NOT include any text or explanations outside the JSON structure.
"""

# Process each row for grading
deepseek = get_deepseek_grader()

# for index, row in df.iloc[:1].iterrows():
for index, row in df.iterrows():
    question = row['question']
    chatbot_response = row['chatbot_response']
    gpt4o_response = row['gpt4o_mini_response']
    
    print(f"Grading question {index+1}/{len(df)}: {question[:50]}...")
    
    # Skip if either response is missing or contains an error
    if (pd.isna(chatbot_response) or pd.isna(gpt4o_response) or 
        "ERROR" in str(chatbot_response) or "ERROR" in str(gpt4o_response)):
        df.at[index, 'grading_feedback'] = "Skipped - one or both responses contain errors"
        continue
    
    # Construct the grading prompt with emphasis on advanced audience
    grading_prompt = f"""
    Question from an ADVANCED-LEVEL user: {question}

    Model 1 Response (Your Chatbot):
    {chatbot_response}

    Model 2 Response (GPT-4o-mini):
    {gpt4o_response}

    Compare and grade these two responses based on how well they serve an ADVANCED-LEVEL user learning DSA concepts.
    Remember that the target audience has mastered fundamental and intermediate concepts and requires expert-level insights, optimizations, and theoretical depth.
    """
    
    try:
        # Send to DeepSeek for grading
        messages = [
            SystemMessage(content=advanced_grading_system_prompt),
            HumanMessage(content=grading_prompt)
        ]
        
        grading_result = deepseek.invoke(messages)
        
        # Parse the grading result
        try:
            grading_json = json.loads(grading_result.content)
            
            # Calculate total scores
            model1_total = grading_json["model1_score"]["total"]
            model2_total = grading_json["model2_score"]["total"]
            
            # Store the results
            df.at[index, 'grading_score'] = f"Chatbot: {model1_total}/25, GPT4o: {model2_total}/25"
            df.at[index, 'grading_feedback'] = grading_result.content
            df.at[index, 'winner'] = grading_json["winner"]
            
        except json.JSONDecodeError:
            # If JSON parsing fails, store the raw response
            df.at[index, 'grading_feedback'] = "JSON parsing error: " + grading_result.content
    
    except Exception as e:
        print(f"Error during grading: {str(e)}")
        df.at[index, 'grading_feedback'] = f"Grading error: {str(e)}"
    
    # Save intermediate results
    if index % 5 == 0 or index == len(df) - 1:
        df.to_csv('advanced_graded_evaluation_results.csv', index=False)
        print(f"Saved grading progress at question {index+1}")
    
    # Add delay to avoid rate limiting
    time.sleep(3)

# Generate summary statistics
if 'winner' in df.columns:
    chatbot_wins = (df['winner'] == 'model1').sum()
    gpt4o_wins = (df['winner'] == 'model2').sum()
    ties = (df['winner'] == 'tie').sum()
    total_evaluated = chatbot_wins + gpt4o_wins + ties
    
    summary_df = pd.DataFrame({
        'Model': ['Your Chatbot', 'GPT-4o-mini', 'Tie'],
        'Wins': [chatbot_wins, gpt4o_wins, ties],
        'Win Percentage': [
            f"{(chatbot_wins/total_evaluated)*100:.1f}%" if total_evaluated > 0 else "N/A",
            f"{(gpt4o_wins/total_evaluated)*100:.1f}%" if total_evaluated > 0 else "N/A",
            f"{(ties/total_evaluated)*100:.1f}%" if total_evaluated > 0 else "N/A"
        ]
    })
    
    # Add average scores by category
    if df['grading_feedback'].notna().any():
        try:
            # Extract and analyze score components from valid feedback
            model1_scores = {"technical_sophistication": [], "optimization_insight": [], 
                            "complexity_analysis": [], "system_level_integration": [], 
                            "research_connections": [], "total": []}
            
            model2_scores = {"technical_sophistication": [], "optimization_insight": [], 
                            "complexity_analysis": [], "system_level_integration": [], 
                            "research_connections": [], "total": []}
            
            for feedback in df['grading_feedback']:
                if isinstance(feedback, str) and not feedback.startswith("Skipped") and not feedback.startswith("JSON parsing error"):
                    try:
                        data = json.loads(feedback)
                        
                        for key in model1_scores.keys():
                            if key in data["model1_score"]:
                                model1_scores[key].append(data["model1_score"][key])
                            
                            if key in data["model2_score"]:
                                model2_scores[key].append(data["model2_score"][key])
                    except:
                        continue
            
            # Calculate averages
            avg_scores_df = pd.DataFrame({
                'Category': list(model1_scores.keys()),
                'Chatbot Avg': [sum(scores)/len(scores) if scores else 0 for scores in model1_scores.values()],
                'GPT-4o-mini Avg': [sum(scores)/len(scores) if scores else 0 for scores in model2_scores.values()]
            })
            
            avg_scores_df.to_csv('advanced_average_scores_by_category.csv', index=False)
            print("\nAverage Scores by Category:")
            print(avg_scores_df)
            
        except Exception as e:
            print(f"Error calculating average scores: {e}")
    
    summary_df.to_csv('advanced_grading_summary.csv', index=False)
    print("\nEvaluation Summary:")
    print(summary_df)

print("Advanced-level grading complete. Results saved to advanced_graded_evaluation_results.csv")