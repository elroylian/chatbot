import sqlite3
from typing import Optional, List, Dict
import uuid
import json

class ChatDatabase:
    def __init__(self, db_path: str = 'chat.db'):
        """Initialize database with specified path."""
        self.db_path = db_path
        self.initialize_database()
    
    def create_connection(self):
        """Create and return a database connection."""
        return sqlite3.connect(self.db_path)

    def initialize_database(self):
        """Create the necessary tables if they don't exist."""
        conn = self.create_connection()
        cursor = conn.cursor()

        # Create users table with UUID
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT DEFAULT '',
                roles TEXT DEFAULT '',
                email TEXT UNIQUE NOT NULL,
                user_level TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Create messages table for chat history with UUID foreign key
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                chat_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        ''')
        
        # Create user analysis table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_analysis (
                user_id TEXT PRIMARY KEY,
                last_analysis_timestamp TIMESTAMP,
                current_level TEXT,
                previous_level TEXT,
                confidence_score FLOAT,
                topics TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
        )

        ''')

        conn.commit()
        conn.close()

    def generate_user_id(self) -> str:
        """Generate a new UUID for user identification."""
        return str(uuid.uuid4())
    
    def get_all_users(self) -> List[Dict]:
        """Get all users from the database."""
        conn = self.create_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id, email, user_level, created_at FROM users')
        users = [{"user_id": user_id, "email": email, "user_level": user_level, "created_at": created_at} for user_id, email, user_level, created_at in cursor.fetchall()]
        
        conn.close()
        return users
    
    def get_all_messages(self) -> List[Dict]:
            """Get all messages from the database."""
            conn = self.create_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT user_id, chat_id, role, content, timestamp FROM messages')
            messages = [{"user_id": user_id, "chat_id": chat_id, "role": role, "content": content, "timestamp": timestamp} for user_id, chat_id, role, content, timestamp in cursor.fetchall()]
            
            conn.close()
            return messages

    def save_user_data(self, user_id: str, user_level: str, email: str, username: str, roles: str) -> bool:
        """
        Save or update user data in the database.
        Returns True if successful, False otherwise.
        """
        conn = self.create_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            INSERT INTO users (user_id, email, user_level, username, roles)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                user_level = excluded.user_level,
                email = COALESCE(excluded.email, users.email)
            ''', (user_id, email, user_level, username, roles))
            
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
        finally:
            conn.close()
            
    def update_user_data(self, user_id: str, user_level: str, email: str) -> bool:
        """
        Update specific user data fields in the database.
        
        Args:
            user_id (str): The unique identifier for the user
            user_level (str): The user's DSA competency level (beginner, intermediate, advanced)
            email (str): The user's email address
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            conn = self.create_connection()
            cursor = conn.cursor()
            
            # Directly update the specified fields
            cursor.execute(
                "UPDATE users SET user_level = ?, email = ? WHERE user_id = ?",
                (user_level, email, user_id)
            )
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"Error updating user data: {str(e)}", exc_info=True)
            return False
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """
        Get user_id, email, user_level, created_at, username, and roles by username.
        Returns None if user not found
        
        """
        conn = self.create_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id, email, user_level, created_at, username, roles FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        
        conn.close()
        
        if result:
            return {
                "user_id": result[0],
                "email": result[1],
                "user_level": result[2],
                "created_at": result[3],
                "username": result[4],
                "roles": result[5]
            }
        return None
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user information by email."""
        conn = self.create_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT user_id, email, user_level, created_at 
        FROM users 
        WHERE email = ?
        ''', (email,))
        result = cursor.fetchone()
        
        conn.close()
        
        if result:
            return {
                "user_id": result[0],
                "email": result[1],
                "user_level": result[2],
                "created_at": result[3]
            }
        return None

    def get_user_level(self, user_id: str) -> str:
        """Get the user's level from the database."""
        conn = self.create_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_level FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        conn.close()
        return result[0] if result else ""

    def save_message(self, user_id: str, chat_id: str, role: str, content: str) -> bool:
        """
        Save a chat message to the database.
        Returns True if successful, False otherwise.
        """
        conn = self.create_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            INSERT INTO messages (user_id, chat_id, role, content)
            VALUES (?, ?, ?, ?)
            ''', (user_id, chat_id, role, content))
            
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
        finally:
            conn.close()

    def load_chat_history(self, user_id: str, chat_id: str) -> List[Dict]:
        """Load chat history for a specific user and chat session."""
        conn = self.create_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT role, content, timestamp
        FROM messages
        WHERE user_id = ? AND chat_id = ?
        ORDER BY timestamp ASC
        ''', (user_id, chat_id))
        
        messages = [{"role": role, "content": content, "timestamp": timestamp} for role, content, timestamp in cursor.fetchall()]
        
        conn.close()
        return messages

    def clear_chat_history(self, user_id: str, chat_id: str) -> bool:
        """Clear chat history for a specific user and chat session."""
        conn = self.create_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            DELETE FROM messages
            WHERE user_id = ? AND chat_id = ?
            ''', (user_id, chat_id))
            
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
        finally:
            conn.close()

    def delete_user(self, user_id: str) -> bool:
        """Delete a user and all their messages from the database."""
        conn = self.create_connection()
        cursor = conn.cursor()
        
        try:
            # Delete user's messages first due to foreign key constraint
            cursor.execute('DELETE FROM messages WHERE user_id = ?', (user_id,))
            cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
            
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
        finally:
            conn.close()

    def user_exists(self, user_id: str) -> bool:
        """Check if a user exists in the database."""
        conn = self.create_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
        exists = cursor.fetchone() is not None
        
        conn.close()
        return exists
    
    def update_user_level(self, user_id: str, new_level: str) -> bool:
        """
        Update the user's competency level in the database.
        Returns True if successful, False otherwise.
        """
        conn = self.create_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
            UPDATE users
            SET user_level = ?
            WHERE user_id = ?
            ''', (new_level, user_id))
            
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
        finally:
            conn.close()
            
    def safe_update_user_level(self, user_id: str, new_level: str) -> bool:
        """
        Safely update the user's level if the user exists.
        """
        if not self.user_exists(user_id):
            print("User not found, cannot update level.")
            return False
        return self.update_user_level(user_id, new_level)
    
    def update_analysis_timestamp(self, user_id):
        """Update the timestamp of the last analysis."""
        conn = self.create_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO user_analysis (user_id, last_analysis_timestamp)
        VALUES (?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            last_analysis_timestamp = CURRENT_TIMESTAMP
        ''', (user_id,))
        
        conn.commit()
        conn.close()

    def get_last_analysis_timestamp(self, user_id):
        """Get the timestamp of the last analysis."""
        conn = self.create_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT last_analysis_timestamp FROM user_analysis WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        conn.close()
        return result[0] if result else None
    
    def reset_analysis_timestamp(self, user_id: str) -> bool:
        """Reset the last analysis timestamp for a given user."""
        conn = self.create_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE user_analysis
                SET last_analysis_timestamp = NULL
                WHERE user_id = ?
            ''', (user_id,))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error while resetting analysis timestamp: {e}")
            return False
        finally:
            conn.close()
    
            
    def get_user_topics(self, user_id: str,) -> List[str]:
        """Update the user's topics in the user_analysis table."""
        conn = self.create_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT topics FROM user_analysis
        WHERE user_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
            

    def append_user_topic(self, user_id: str, parent_topic: str, subtopic: str) -> bool:
        """
        Append a subtopic under a given parent topic for the user in the user_analysis table.
        If the parent topic doesn't exist, it creates a new entry.
        """
        conn = self.create_connection()
        cursor = conn.cursor()
        try:
            # Fetch current topics JSON for the user
            cursor.execute("SELECT topics FROM user_analysis WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row and row[0]:
                topics_dict = json.loads(row[0])
            else:
                topics_dict = {}
            
            # Append the subtopic under the specified parent topic
            if parent_topic in topics_dict:
                if subtopic not in topics_dict[parent_topic]:
                    topics_dict[parent_topic].append(subtopic)
            else:
                topics_dict[parent_topic] = [subtopic]
            
            # Convert the dictionary back to a JSON string
            topics_json = json.dumps(topics_dict)
            
            # Update the database: if the user exists, update topics; if not, insert a new record
            cursor.execute('''
                INSERT INTO user_analysis (user_id, topics)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET topics = excluded.topics
            ''', (user_id, topics_json))
            
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error while appending topics: {e}")
            return False
        finally:
            conn.close()
    
    def update_user_topics(self, user_id: str, topics: Dict[str, List[str]]) -> bool:
        conn = self.create_connection()
        cursor = conn.cursor()
        try:
            topics_json = json.dumps(topics)
            cursor.execute('''
            INSERT INTO user_analysis (user_id, topics)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET topics = excluded.topics
            ''', (user_id, topics_json))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
        finally:
            conn.close()



