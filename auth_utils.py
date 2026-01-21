"""
Authentication utilities untuk local SQLite database
Menggantikan Supabase auth completely
"""
import sqlite3
import hashlib
import secrets
import string
from datetime import datetime, timedelta
import os

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'cofind.db')

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
    except sqlite3.Error:
        pass
    return conn

def hash_password(password: str) -> str:
    """Hash password dengan SHA256 + salt"""
    salt = secrets.token_hex(32)
    pwd_hash = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${pwd_hash}"

def verify_password(password: str, password_hash: str) -> bool:
    """Verify password"""
    try:
        salt, pwd_hash = password_hash.split('$')
        return hashlib.sha256((salt + password).encode()).hexdigest() == pwd_hash
    except:
        return False

def generate_token(length: int = 64) -> str:
    """Generate secure session token"""
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

def signup(email: str, username: str, password: str, full_name: str = "") -> dict:
    """Register new user"""
    try:
        # Validate input
        if not email or not username or not password:
            return {'success': False, 'error': 'Missing required fields'}
        
        if len(password) < 6:
            return {'success': False, 'error': 'Password must be at least 6 characters'}
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if email already exists
            cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
            if cursor.fetchone():
                return {'success': False, 'error': 'Email already registered'}
            
            # Check if username already exists
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            if cursor.fetchone():
                return {'success': False, 'error': 'Username already taken'}
            
            # Create user
            password_hash = hash_password(password)
            cursor.execute('''
                INSERT INTO users (email, username, password_hash)
                VALUES (?, ?, ?)
            ''', (email, username, password_hash))
            
            user_id = cursor.lastrowid
            
            # Create user profile
            cursor.execute('''
                INSERT INTO user_profiles (user_id, full_name)
                VALUES (?, ?)
            ''', (user_id, full_name))
            
            # Create session token
            token = generate_token()
            expires_at = datetime.utcnow() + timedelta(days=30)
            cursor.execute('''
                INSERT INTO sessions (user_id, token, expires_at)
                VALUES (?, ?, ?)
            ''', (user_id, token, expires_at.strftime('%Y-%m-%d %H:%M:%S')))
            
            # Get user info
            cursor.execute('''
                SELECT u.id, u.username, u.email, p.full_name
                FROM users u
                LEFT JOIN user_profiles p ON u.id = p.user_id
                WHERE u.id = ?
            ''', (user_id,))
            user = dict(cursor.fetchone())
        
        return {
            'success': True,
            'user': user,
            'token': token,
            'expires_in': 30 * 24 * 60 * 60  # 30 days in seconds
        }
    
    except Exception as e:
        return {'success': False, 'error': str(e)}

def login(email: str, password: str) -> dict:
    """Login user"""
    try:
        if not email or not password:
            return {'success': False, 'error': 'Email and password required'}
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Find user by email
            cursor.execute('''
                SELECT u.id, u.email, u.username, u.password_hash, u.is_admin, p.full_name
                FROM users u
                LEFT JOIN user_profiles p ON u.id = p.user_id
                WHERE u.email = ? AND u.is_active = 1
            ''', (email,))
            
            row = cursor.fetchone()
            if not row:
                return {'success': False, 'error': 'Invalid email or password'}
            
            user = dict(row)
            password_hash = user.pop('password_hash')
            
            # Verify password
            if not verify_password(password, password_hash):
                return {'success': False, 'error': 'Invalid email or password'}
            
            # Create session token
            token = generate_token()
            expires_at = datetime.utcnow() + timedelta(days=30)
            cursor.execute('''
                INSERT INTO sessions (user_id, token, expires_at)
                VALUES (?, ?, ?)
            ''', (user['id'], token, expires_at.strftime('%Y-%m-%d %H:%M:%S')))
        
        return {
            'success': True,
            'user': user,
            'token': token,
            'expires_in': 30 * 24 * 60 * 60  # 30 days in seconds
        }
    
    except Exception as e:
        return {'success': False, 'error': str(e)}

def verify_token(token: str) -> dict:
    """Verify session token and return user info"""
    try:
        if not token:
            return {'valid': False, 'user': None}
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Find session by token
            cursor.execute('''
                SELECT u.id, u.username, u.email, u.is_admin, p.full_name, s.expires_at
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                LEFT JOIN user_profiles p ON u.id = p.user_id
                WHERE s.token = ? AND s.expires_at > datetime('now') AND u.is_active = 1
            ''', (token,))
            
            row = cursor.fetchone()
        
        if not row:
            return {'valid': False, 'user': None}
        
        user = dict(row)
        user.pop('expires_at', None)
        
        return {'valid': True, 'user': user}
    
    except Exception as e:
        return {'valid': False, 'error': str(e)}

def logout(token: str) -> dict:
    """Delete session token"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM sessions WHERE token = ?', (token,))
        
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_user_by_id(user_id: int) -> dict:
    """Get user info by ID"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT u.id, u.username, u.email, u.is_admin, p.full_name, p.avatar_url, p.bio, p.phone
                FROM users u
                LEFT JOIN user_profiles p ON u.id = p.user_id
                WHERE u.id = ? AND u.is_active = 1
            ''', (user_id,))
            
            row = cursor.fetchone()
        
        if not row:
            return None
        
        return dict(row)
    
    except Exception as e:
        return None

def update_user_profile(user_id: int, full_name: str = None, bio: str = None, 
                       avatar_url: str = None, phone: str = None) -> dict:
    """Update user profile"""
    try:
        updates = []
        values = []
        
        if full_name is not None:
            updates.append('full_name = ?')
            values.append(full_name)
        if bio is not None:
            updates.append('bio = ?')
            values.append(bio)
        if avatar_url is not None:
            updates.append('avatar_url = ?')
            values.append(avatar_url)
        if phone is not None:
            updates.append('phone = ?')
            values.append(phone)
        
        if not updates:
            return {'success': True}
        
        updates.append('updated_at = CURRENT_TIMESTAMP')
        values.append(user_id)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = f"UPDATE user_profiles SET {', '.join(updates)} WHERE user_id = ?"
            cursor.execute(query, values)
        
        return {'success': True}
    
    except Exception as e:
        return {'success': False, 'error': str(e)}

def update_password(user_id: int, old_password: str, new_password: str) -> dict:
    """Update user password"""
    try:
        if not old_password or not new_password:
            return {'success': False, 'error': 'Both passwords required'}
        
        if len(new_password) < 6:
            return {'success': False, 'error': 'New password must be at least 6 characters'}
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get current password hash
            cursor.execute('SELECT password_hash FROM users WHERE id = ?', (user_id,))
            row = cursor.fetchone()
            
            if not row:
                return {'success': False, 'error': 'User not found'}
            
            # Verify old password
            if not verify_password(old_password, row[0]):
                return {'success': False, 'error': 'Invalid current password'}
            
            # Update to new password
            new_hash = hash_password(new_password)
            cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_hash, user_id))
        
        return {'success': True}
    
    except Exception as e:
        return {'success': False, 'error': str(e)}
