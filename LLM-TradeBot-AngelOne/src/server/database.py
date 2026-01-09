"""
Database module for user and broker credentials storage
Uses SQLite for simplicity
"""

import sqlite3
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any
from loguru import logger

# Database path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'tradebot.db')

def get_db_connection():
    """Get database connection"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize database tables"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Users table with broker credentials
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL DEFAULT 'default',
            client_id TEXT,
            api_key TEXT,
            pin TEXT,
            broker_token TEXT,
            refresh_token TEXT,
            feed_token TEXT,
            token_expiry TEXT,
            is_connected INTEGER DEFAULT 0,
            llm_provider TEXT DEFAULT 'deepseek',
            deepseek_api_key TEXT,
            openai_api_key TEXT,
            claude_api_key TEXT,
            qwen_api_key TEXT,
            gemini_api_key TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Add new columns if they don't exist (for existing databases)
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN refresh_token TEXT')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN feed_token TEXT')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN llm_provider TEXT DEFAULT "deepseek"')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN deepseek_api_key TEXT')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN openai_api_key TEXT')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN claude_api_key TEXT')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN qwen_api_key TEXT')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN gemini_api_key TEXT')
    except:
        pass
    
    # Settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            key TEXT NOT NULL,
            value TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, key)
        )
    ''')
    
    # Create default user if not exists
    cursor.execute('SELECT id FROM users WHERE username = ?', ('default',))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO users (username) VALUES (?)', ('default',))
    
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {DB_PATH}")

def get_user(username: str = 'default') -> Optional[Dict]:
    """Get user by username"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def save_broker_credentials(client_id: str, api_key: str, pin: str, username: str = 'default') -> bool:
    """Save broker credentials"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE users 
            SET client_id = ?, api_key = ?, pin = ?, updated_at = ?
            WHERE username = ?
        ''', (client_id, api_key, pin, datetime.now().isoformat(), username))
        
        if cursor.rowcount == 0:
            cursor.execute('''
                INSERT INTO users (username, client_id, api_key, pin)
                VALUES (?, ?, ?, ?)
            ''', (username, client_id, api_key, pin))
        
        conn.commit()
        logger.info(f"Broker credentials saved for {username}")
        return True
    except Exception as e:
        logger.error(f"Failed to save credentials: {e}")
        return False
    finally:
        conn.close()

def save_broker_token(token: str, refresh_token: str = None, feed_token: str = None, expiry: str = None, username: str = 'default') -> bool:
    """Save broker session tokens after successful login"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE users 
            SET broker_token = ?, refresh_token = ?, feed_token = ?, token_expiry = ?, is_connected = 1, updated_at = ?
            WHERE username = ?
        ''', (token, refresh_token, feed_token, expiry, datetime.now().isoformat(), username))
        
        conn.commit()
        logger.info(f"Broker tokens saved for {username}")
        return True
    except Exception as e:
        logger.error(f"Failed to save token: {e}")
        return False
    finally:
        conn.close()

def clear_broker_token(username: str = 'default') -> bool:
    """Clear broker token on disconnect"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE users 
            SET broker_token = NULL, token_expiry = NULL, is_connected = 0, updated_at = ?
            WHERE username = ?
        ''', (datetime.now().isoformat(), username))
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to clear token: {e}")
        return False
    finally:
        conn.close()

def get_broker_credentials(username: str = 'default') -> Optional[Dict]:
    """Get broker credentials for a user"""
    user = get_user(username)
    if user:
        return {
            'client_id': user.get('client_id'),
            'api_key': user.get('api_key'),
            'pin': user.get('pin'),
            'broker_token': user.get('broker_token'),
            'refresh_token': user.get('refresh_token'),
            'feed_token': user.get('feed_token'),
            'token_expiry': user.get('token_expiry'),
            'is_connected': bool(user.get('is_connected'))
        }
    return None

def save_setting(key: str, value: Any, username: str = 'default') -> bool:
    """Save a setting"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get user id
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        if not user:
            return False
        
        user_id = user['id']
        value_str = json.dumps(value) if not isinstance(value, str) else value
        
        cursor.execute('''
            INSERT OR REPLACE INTO settings (user_id, key, value)
            VALUES (?, ?, ?)
        ''', (user_id, key, value_str))
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to save setting: {e}")
        return False
    finally:
        conn.close()

def get_setting(key: str, username: str = 'default') -> Optional[Any]:
    """Get a setting"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT s.value FROM settings s
            JOIN users u ON s.user_id = u.id
            WHERE u.username = ? AND s.key = ?
        ''', (username, key))
        
        row = cursor.fetchone()
        if row:
            try:
                return json.loads(row['value'])
            except:
                return row['value']
        return None
    finally:
        conn.close()

def save_llm_settings(llm_provider: str, api_key: str, username: str = 'default') -> bool:
    """Save LLM provider and API key"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Map provider to column name
        provider_column_map = {
            'deepseek': 'deepseek_api_key',
            'openai': 'openai_api_key',
            'claude': 'claude_api_key',
            'qwen': 'qwen_api_key',
            'gemini': 'gemini_api_key'
        }
        
        api_key_column = provider_column_map.get(llm_provider.lower(), 'deepseek_api_key')
        
        # Update LLM provider and the specific API key
        cursor.execute(f'''
            UPDATE users 
            SET llm_provider = ?, {api_key_column} = ?, updated_at = ?
            WHERE username = ?
        ''', (llm_provider.lower(), api_key, datetime.now().isoformat(), username))
        
        conn.commit()
        logger.info(f"LLM settings saved: provider={llm_provider}")
        
        # Also update environment variable for immediate effect
        import os
        os.environ['LLM_PROVIDER'] = llm_provider.lower()
        
        env_key_map = {
            'deepseek': 'DEEPSEEK_API_KEY',
            'openai': 'OPENAI_API_KEY',
            'claude': 'CLAUDE_API_KEY',
            'qwen': 'QWEN_API_KEY',
            'gemini': 'GEMINI_API_KEY'
        }
        env_key = env_key_map.get(llm_provider.lower(), 'DEEPSEEK_API_KEY')
        os.environ[env_key] = api_key
        
        return True
    except Exception as e:
        logger.error(f"Failed to save LLM settings: {e}")
        return False
    finally:
        conn.close()

def get_llm_settings(username: str = 'default') -> Optional[Dict]:
    """Get LLM settings for a user"""
    user = get_user(username)
    if user:
        return {
            'llm_provider': user.get('llm_provider', 'deepseek'),
            'deepseek_api_key': user.get('deepseek_api_key'),
            'openai_api_key': user.get('openai_api_key'),
            'claude_api_key': user.get('claude_api_key'),
            'qwen_api_key': user.get('qwen_api_key'),
            'gemini_api_key': user.get('gemini_api_key')
        }
    return None

def load_llm_settings_to_env(username: str = 'default'):
    """Load LLM settings from database to environment variables on startup"""
    import os
    settings = get_llm_settings(username)
    if settings:
        provider = settings.get('llm_provider', 'deepseek')
        os.environ['LLM_PROVIDER'] = provider
        
        # Load all API keys to environment
        key_map = {
            'deepseek_api_key': 'DEEPSEEK_API_KEY',
            'openai_api_key': 'OPENAI_API_KEY',
            'claude_api_key': 'CLAUDE_API_KEY',
            'qwen_api_key': 'QWEN_API_KEY',
            'gemini_api_key': 'GEMINI_API_KEY'
        }
        
        for db_key, env_key in key_map.items():
            if settings.get(db_key):
                os.environ[env_key] = settings[db_key]
        
        logger.info(f"LLM settings loaded from database: provider={provider}")

# Initialize database on import
init_database()
