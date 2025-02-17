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
                    "user": messages[i].content,
                    "assistant": messages[i+1].content,
                })
    
    prompt = PromptTemplate(
        template="""Assess the user's understanding and progress based on their complete interactions.

Current Level: {user_level}

Conversation History:
{conversation_pairs}

Return ONLY a JSON object in this exact format:
{{
    "current_level": "{user_level}",
    "recommendation": "Promote/Maintain/Demote",
    "confidence": 0.0-1.0,
    "evidence": ["specific interaction showing understanding", "another specific interaction"],
    "reasoning": ["detailed reason for recommendation", "additional reason"]
}}

Assess:
1. Technical Accuracy:
   - Correct use of DSA terminology
   - Accuracy in problem-solving attempts
   - Understanding of concept relationships

2. Depth of Understanding:
   - Quality of their explanations
   - Ability to apply concepts
   - Response to chatbot's explanations
   - Follow-up questions showing comprehension

3. Learning Progression:
   - Improvement in question quality
   - Better understanding shown over time
   - Application of previous learning

Only recommend level changes with strong evidence (confidence > 0.8)
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
            f"User: {pair['user']}\nAssistant: {pair['assistant']}\n"
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