from typing import Annotated, Sequence, Dict, Any, List
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from langgraph.graph import END, StateGraph, START
import streamlit as st

class AgentState(TypedDict):
    """State management for level assessment"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_level: str

class LevelAssessment(BaseModel):
    current_level: str = Field(description="User's current level")
    recommendation: str = Field(description="Promote/Maintain/Demote")
    confidence: float = Field(description="Confidence score 0-1")
    evidence: List[str] = Field(description="Supporting evidence from questions")
    reasoning: List[str] = Field(description="Reasons for recommendation")

def analyze_user_level(state: AgentState) -> Dict[str, Any]:
    """Analyze if user level should change based on full interaction context"""
    messages = state["messages"]
    user_level = state["user_level"]
    
    # Extract conversation pairs for context
    conversation_pairs = []
    for i in range(0, len(messages)-1, 2):
        if i+1 < len(messages):
            if isinstance(messages[i], HumanMessage) and isinstance(messages[i+1], AIMessage):
                conversation_pairs.append({
                    "question": messages[i].content,
                    "response": messages[i+1].content,
                    "follow_up": messages[i+2].content if i+2 < len(messages) else None
                })
    
    prompt = PromptTemplate(
        template="""Assess the user's learning progression based on their interactions.

Current Level: {user_level}

Level Definitions:
- Beginner: Basic questions about concepts, needs step-by-step explanations
- Intermediate: Implementation questions, understands and applies concepts
- Advanced: Complex questions, optimization focus, deep technical discussions

Conversation:
{conversation_pairs}

Assessment Criteria:
1. Learning Progression:
   - Does the user ask follow-up questions?
   - Do questions become more complex over time?
   - Are they applying concepts from previous answers?

2. Understanding Depth:
   - Do they ask for implementation after understanding concepts?
   - Can they connect different concepts together?
   - Do they show curiosity about optimization?

3. Interaction Quality:
   - Simple questions vs detailed inquiries
   - Passive learning vs active engagement
   - Basic terms vs technical terminology

Return ONLY a JSON object in this exact format:
{{
    "current_level": "{user_level}",
    "recommendation": "Promote/Maintain/Demote",
    "confidence": 0.0-1.0,
    "evidence": ["specific interaction showing progress/regression", "another interaction"],
    "reasoning": ["detailed reason for recommendation", "additional reason"]
}}

Note: Require at least 3 meaningful interactions before suggesting promotion/demotion.
""",
        input_variables=["conversation_pairs", "user_level"]
    )
    
    try:
        model = ChatOpenAI(
            model_name="gpt-4o-mini",
            temperature=0,
            streaming=True,
            api_key=st.secrets["OpenAI_key"]
        )
        llm_with_analysis = model.with_structured_output(LevelAssessment)
        
        # Format conversation pairs for prompt
        conversation_text = "\n".join([
            f"Question: {pair['question']}"
            for pair in conversation_pairs
        ])
        
        
        analysis = llm_with_analysis.invoke(prompt.format(
            conversation_pairs=conversation_text,
            user_level=user_level
        ))
        
        return {"messages": [AIMessage(content=str(analysis))]}
        
    except Exception as e:
        print(f"Error in analysis: {str(e)}")
        return {"messages": [AIMessage(content="Error analyzing user level")]}

# Graph setup
workflow = StateGraph(AgentState)
workflow.add_node("analyze", analyze_user_level)
workflow.add_edge(START, "analyze")
workflow.add_edge("analyze", END)

# Compile
from langgraph.checkpoint.memory import MemorySaver
memory = MemorySaver()
graph = workflow.compile(memory)