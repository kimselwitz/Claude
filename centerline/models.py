"""
Database models for Centerline Barn Management System
"""
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional


class Database:
    """Database connection handler"""

    def __init__(self, db_path: str = "centerline.db"):
        self.db_path = db_path

    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initialize database schema"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Create Clients table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                horse_assignment TEXT,
                active BOOLEAN NOT NULL DEFAULT 1,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create Services table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_name TEXT NOT NULL,
                price DECIMAL(10, 2) NOT NULL,
                billing_frequency TEXT NOT NULL,
                active BOOLEAN NOT NULL DEFAULT 1
            )
        ''')

        # Create Transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                service_id INTEGER,
                amount DECIMAL(10, 2) NOT NULL,
                transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                transaction_type TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY (client_id) REFERENCES clients(id),
                FOREIGN KEY (service_id) REFERENCES services(id)
            )
        ''')

        # Create Users table for authentication and messaging
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                client_id INTEGER,
                role TEXT NOT NULL DEFAULT 'client',
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients(id)
            )
        ''')

        # Create Chat Groups table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                is_broadcast BOOLEAN NOT NULL DEFAULT 0,
                created_by INTEGER NOT NULL,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        ''')

        # Create Group Members table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_admin BOOLEAN NOT NULL DEFAULT 0,
                FOREIGN KEY (group_id) REFERENCES chat_groups(id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(group_id, user_id)
            )
        ''')

        # Create Messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                recipient_id INTEGER,
                group_id INTEGER,
                message_text TEXT NOT NULL,
                is_broadcast BOOLEAN NOT NULL DEFAULT 0,
                is_read BOOLEAN NOT NULL DEFAULT 0,
                sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users(id),
                FOREIGN KEY (recipient_id) REFERENCES users(id),
                FOREIGN KEY (group_id) REFERENCES chat_groups(id)
            )
        ''')

        conn.commit()
        conn.close()


class Client:
    """Client model"""

    def __init__(self, db: Database):
        self.db = db

    def get_all(self, active_only: bool = True) -> List[Dict]:
        """Get all clients"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        if active_only:
            cursor.execute('SELECT * FROM clients WHERE active = 1 ORDER BY name')
        else:
            cursor.execute('SELECT * FROM clients ORDER BY name')

        clients = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return clients

    def get_by_id(self, client_id: int) -> Optional[Dict]:
        """Get client by ID"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM clients WHERE id = ?', (client_id,))
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def create(self, name: str, email: str = '', phone: str = '',
               horse_assignment: str = '', active: bool = True) -> int:
        """Create new client"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO clients (name, email, phone, horse_assignment, active)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, email, phone, horse_assignment, active))

        client_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return client_id

    def update(self, client_id: int, name: str, email: str = '',
               phone: str = '', horse_assignment: str = '', active: bool = True):
        """Update client"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE clients
            SET name = ?, email = ?, phone = ?, horse_assignment = ?, active = ?
            WHERE id = ?
        ''', (name, email, phone, horse_assignment, active, client_id))

        conn.commit()
        conn.close()

    def get_balance(self, client_id: int) -> float:
        """Get client balance (charges - payments)"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Sum all charges
        cursor.execute('''
            SELECT COALESCE(SUM(amount), 0) as total
            FROM transactions
            WHERE client_id = ? AND transaction_type = 'charge'
        ''', (client_id,))
        charges = cursor.fetchone()['total']

        # Sum all payments
        cursor.execute('''
            SELECT COALESCE(SUM(amount), 0) as total
            FROM transactions
            WHERE client_id = ? AND transaction_type = 'payment'
        ''', (client_id,))
        payments = cursor.fetchone()['total']

        conn.close()
        return float(charges - payments)


class Service:
    """Service model"""

    def __init__(self, db: Database):
        self.db = db

    def get_all(self, active_only: bool = True) -> List[Dict]:
        """Get all services"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        if active_only:
            cursor.execute('SELECT * FROM services WHERE active = 1 ORDER BY service_name')
        else:
            cursor.execute('SELECT * FROM services ORDER BY service_name')

        services = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return services

    def get_by_id(self, service_id: int) -> Optional[Dict]:
        """Get service by ID"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM services WHERE id = ?', (service_id,))
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def create(self, service_name: str, price: float,
               billing_frequency: str, active: bool = True) -> int:
        """Create new service"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO services (service_name, price, billing_frequency, active)
            VALUES (?, ?, ?, ?)
        ''', (service_name, price, billing_frequency, active))

        service_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return service_id

    def update(self, service_id: int, service_name: str, price: float,
               billing_frequency: str, active: bool = True):
        """Update service"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE services
            SET service_name = ?, price = ?, billing_frequency = ?, active = ?
            WHERE id = ?
        ''', (service_name, price, billing_frequency, active, service_id))

        conn.commit()
        conn.close()


class Transaction:
    """Transaction model"""

    def __init__(self, db: Database):
        self.db = db

    def get_all(self, client_id: Optional[int] = None) -> List[Dict]:
        """Get all transactions, optionally filtered by client"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        if client_id:
            cursor.execute('''
                SELECT t.*, c.name as client_name, s.service_name
                FROM transactions t
                JOIN clients c ON t.client_id = c.id
                LEFT JOIN services s ON t.service_id = s.id
                WHERE t.client_id = ?
                ORDER BY t.transaction_date DESC
            ''', (client_id,))
        else:
            cursor.execute('''
                SELECT t.*, c.name as client_name, s.service_name
                FROM transactions t
                JOIN clients c ON t.client_id = c.id
                LEFT JOIN services s ON t.service_id = s.id
                ORDER BY t.transaction_date DESC
            ''')

        transactions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return transactions

    def create(self, client_id: int, amount: float, transaction_type: str,
               service_id: Optional[int] = None, notes: str = '') -> int:
        """Create new transaction"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO transactions (client_id, service_id, amount, transaction_type, notes)
            VALUES (?, ?, ?, ?, ?)
        ''', (client_id, service_id, amount, transaction_type, notes))

        transaction_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return transaction_id


class User:
    """User model for authentication and messaging"""

    def __init__(self, db: Database):
        self.db = db

    def get_all(self) -> List[Dict]:
        """Get all users"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT u.*, c.name as client_name
            FROM users u
            LEFT JOIN clients c ON u.client_id = c.id
            ORDER BY u.username
        ''')

        users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return users

    def get_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT u.*, c.name as client_name
            FROM users u
            LEFT JOIN clients c ON u.client_id = c.id
            WHERE u.id = ?
        ''', (user_id,))
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def get_by_username(self, username: str) -> Optional[Dict]:
        """Get user by username"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def create(self, username: str, password: str, role: str = 'client',
               client_id: Optional[int] = None) -> int:
        """Create new user (password should be pre-hashed)"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO users (username, password_hash, role, client_id)
            VALUES (?, ?, ?, ?)
        ''', (username, password, role, client_id))

        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return user_id

    def update_last_seen(self, user_id: int):
        """Update last seen timestamp"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE id = ?
        ''', (user_id,))

        conn.commit()
        conn.close()

    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        user = self.get_by_id(user_id)
        return user and user['role'] == 'admin'


class ChatGroup:
    """Chat group model"""

    def __init__(self, db: Database):
        self.db = db

    def get_all(self) -> List[Dict]:
        """Get all chat groups"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT cg.*, u.username as creator_name,
                   COUNT(DISTINCT gm.user_id) as member_count
            FROM chat_groups cg
            JOIN users u ON cg.created_by = u.id
            LEFT JOIN group_members gm ON cg.id = gm.group_id
            GROUP BY cg.id
            ORDER BY cg.created_date DESC
        ''')

        groups = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return groups

    def get_by_id(self, group_id: int) -> Optional[Dict]:
        """Get chat group by ID"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT cg.*, u.username as creator_name
            FROM chat_groups cg
            JOIN users u ON cg.created_by = u.id
            WHERE cg.id = ?
        ''', (group_id,))
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def get_user_groups(self, user_id: int) -> List[Dict]:
        """Get all groups user is a member of"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT cg.*, gm.is_admin as user_is_admin,
                   COUNT(DISTINCT gm2.user_id) as member_count
            FROM chat_groups cg
            JOIN group_members gm ON cg.id = gm.group_id
            LEFT JOIN group_members gm2 ON cg.id = gm2.group_id
            WHERE gm.user_id = ?
            GROUP BY cg.id
            ORDER BY cg.name
        ''', (user_id,))

        groups = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return groups

    def create(self, name: str, created_by: int, description: str = '',
               is_broadcast: bool = False) -> int:
        """Create new chat group"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO chat_groups (name, description, is_broadcast, created_by)
            VALUES (?, ?, ?, ?)
        ''', (name, description, is_broadcast, created_by))

        group_id = cursor.lastrowid

        # Add creator as admin member
        cursor.execute('''
            INSERT INTO group_members (group_id, user_id, is_admin)
            VALUES (?, ?, 1)
        ''', (group_id, created_by))

        conn.commit()
        conn.close()
        return group_id

    def add_member(self, group_id: int, user_id: int, is_admin: bool = False):
        """Add member to group"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR IGNORE INTO group_members (group_id, user_id, is_admin)
            VALUES (?, ?, ?)
        ''', (group_id, user_id, is_admin))

        conn.commit()
        conn.close()

    def remove_member(self, group_id: int, user_id: int):
        """Remove member from group"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            DELETE FROM group_members WHERE group_id = ? AND user_id = ?
        ''', (group_id, user_id))

        conn.commit()
        conn.close()

    def get_members(self, group_id: int) -> List[Dict]:
        """Get all members of a group"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT u.id, u.username, u.role, gm.is_admin, gm.joined_date,
                   c.name as client_name
            FROM group_members gm
            JOIN users u ON gm.user_id = u.id
            LEFT JOIN clients c ON u.client_id = c.id
            WHERE gm.group_id = ?
            ORDER BY gm.is_admin DESC, u.username
        ''', (group_id,))

        members = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return members


class Message:
    """Message model"""

    def __init__(self, db: Database):
        self.db = db

    def create(self, sender_id: int, message_text: str,
               recipient_id: Optional[int] = None,
               group_id: Optional[int] = None,
               is_broadcast: bool = False) -> int:
        """Create new message"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO messages (sender_id, recipient_id, group_id, message_text, is_broadcast)
            VALUES (?, ?, ?, ?, ?)
        ''', (sender_id, recipient_id, group_id, message_text, is_broadcast))

        message_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return message_id

    def get_direct_messages(self, user1_id: int, user2_id: int) -> List[Dict]:
        """Get direct messages between two users"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT m.*,
                   s.username as sender_name,
                   r.username as recipient_name
            FROM messages m
            JOIN users s ON m.sender_id = s.id
            LEFT JOIN users r ON m.recipient_id = r.id
            WHERE m.group_id IS NULL
              AND ((m.sender_id = ? AND m.recipient_id = ?)
                   OR (m.sender_id = ? AND m.recipient_id = ?))
            ORDER BY m.sent_date ASC
        ''', (user1_id, user2_id, user2_id, user1_id))

        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return messages

    def get_group_messages(self, group_id: int, limit: int = 100) -> List[Dict]:
        """Get messages for a group"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT m.*, u.username as sender_name
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.group_id = ?
            ORDER BY m.sent_date DESC
            LIMIT ?
        ''', (group_id, limit))

        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return list(reversed(messages))  # Return in chronological order

    def get_broadcasts(self, limit: int = 50) -> List[Dict]:
        """Get broadcast messages"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT m.*, u.username as sender_name
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.is_broadcast = 1
            ORDER BY m.sent_date DESC
            LIMIT ?
        ''', (limit,))

        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return messages

    def get_user_conversations(self, user_id: int) -> List[Dict]:
        """Get list of users that have conversations with this user"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT DISTINCT
                CASE
                    WHEN m.sender_id = ? THEN m.recipient_id
                    ELSE m.sender_id
                END as other_user_id,
                u.username,
                c.name as client_name,
                MAX(m.sent_date) as last_message_date,
                COUNT(CASE WHEN m.recipient_id = ? AND m.is_read = 0 THEN 1 END) as unread_count
            FROM messages m
            JOIN users u ON (
                CASE
                    WHEN m.sender_id = ? THEN m.recipient_id
                    ELSE m.sender_id
                END = u.id
            )
            LEFT JOIN clients c ON u.client_id = c.id
            WHERE (m.sender_id = ? OR m.recipient_id = ?)
              AND m.group_id IS NULL
              AND m.is_broadcast = 0
            GROUP BY other_user_id
            ORDER BY last_message_date DESC
        ''', (user_id, user_id, user_id, user_id, user_id))

        conversations = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return conversations

    def mark_as_read(self, message_id: int):
        """Mark message as read"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE messages SET is_read = 1 WHERE id = ?
        ''', (message_id,))

        conn.commit()
        conn.close()

    def mark_conversation_as_read(self, user_id: int, other_user_id: int):
        """Mark all messages in a conversation as read"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE messages
            SET is_read = 1
            WHERE sender_id = ? AND recipient_id = ? AND is_read = 0
        ''', (other_user_id, user_id))

        conn.commit()
        conn.close()

    def get_unread_count(self, user_id: int) -> int:
        """Get count of unread messages for user"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT COUNT(*) as count
            FROM messages
            WHERE recipient_id = ? AND is_read = 0
        ''', (user_id,))

        result = cursor.fetchone()
        conn.close()
        return result['count'] if result else 0
