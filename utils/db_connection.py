import sqlite3
from typing import Optional, List, Dict
import uuid

class ChatDatabase:
    def __init__(self, db_path: str = 'dsa_chatbot.db'):
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

    def save_user_data(self, user_id: str, user_level: str, email: str) -> bool:
        """
        Save or update user data in the database.
        Returns True if successful, False otherwise.
        """
        conn = self.create_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            INSERT INTO users (user_id, email, user_level)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                user_level = excluded.user_level,
                email = COALESCE(excluded.email, users.email)
            ''', (user_id, email, user_level))
            
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
        finally:
            conn.close()

    def create_new_user(self, email: str, user_level: str = '') -> Optional[str]:
        """
        Create a new user and return their UUID.
        Returns None if creation fails.
        """
        user_id = self.generate_user_id()
        if self.save_user_data(user_id, user_level, email):
            return user_id
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
        
        messages = [{"role": role, "content": content} for role, content, _ in cursor.fetchall()]
        
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

