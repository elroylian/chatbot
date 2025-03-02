from datetime import datetime, timedelta
from utils.db_connection import ChatDatabase

# Constants
TIME_DELTA = 7  # Days
NUM_INTERACTIONS = 2

db = ChatDatabase("chat.db")

def should_analyze_user_level(user_id):
    """Determine if it's time to analyze the user's level."""
    last_analysis = db.get_last_analysis_timestamp(user_id)
    
    # If no previous analysis, definitely analyze
    if last_analysis is None:
        db.update_analysis_timestamp(user_id)
        return False
        
    
    # Get recent interactions count
    recent_history = db.load_chat_history(user_id, f"{user_id}_1")
    last_analysis_datetime = datetime.fromisoformat(last_analysis) if isinstance(last_analysis, str) else last_analysis
    
    # Count only messages after last analysis
    interaction_count = 0
    for message in recent_history:
        message_timestamp = message.get("timestamp")
        
        # Convert string timestamp to datetime
        message_datetime = datetime.fromisoformat(message_timestamp)
        
        
        if message_datetime and message["role"] == "user":
            if message_datetime > last_analysis_datetime:
                interaction_count += 1
    
    # Criteria: At least 7 days and 10 interactions since last analysis
    time_threshold = datetime.now() - last_analysis_datetime >= timedelta(days=TIME_DELTA)
    interaction_threshold = interaction_count >= NUM_INTERACTIONS
    # print("Last Analysis: ", last_analysis_datetime)
    print("Should Analyze: ", time_threshold or interaction_threshold)
    print("Time Threshold: ", time_threshold)
    print("Interaction Threshold: ", interaction_threshold)
    
    return time_threshold or interaction_threshold

def get_next_level(current_level):
    """Get the next higher level from the current one."""
    levels = ["beginner", "intermediate", "advanced"]
    try:
        current_index = levels.index(current_level.lower())
        if current_index < len(levels) - 1:
            return levels[current_index + 1]
        return current_level  # Already at highest level
    except ValueError:
        return "beginner"  # Default if level not found

def get_previous_level(current_level):
    """Get the previous lower level from the current one."""
    levels = ["beginner", "intermediate", "advanced"]
    try:
        current_index = levels.index(current_level.lower())
        if current_index > 0:
            return levels[current_index - 1]
        return current_level  # Already at lowest level
    except ValueError:
        return "beginner"  # Default if level not found