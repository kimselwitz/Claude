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
