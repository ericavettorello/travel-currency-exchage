import sqlite3
import sys
from datetime import datetime
from typing import Optional, List, Dict, Tuple

# Устанавливаем кодировку UTF-8 для вывода в консоль Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')


class Database:
    def __init__(self, db_name: str = "travel_wallet.db"):
        """Инициализация базы данных"""
        self.db_name = db_name
        self.init_db()
    
    def get_connection(self):
        """Получить соединение с базой данных"""
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Инициализация таблиц базы данных"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица путешествий
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                from_country TEXT NOT NULL,
                to_country TEXT NOT NULL,
                from_currency TEXT NOT NULL,
                to_currency TEXT NOT NULL,
                exchange_rate REAL NOT NULL,
                balance_from REAL DEFAULT 0,
                balance_to REAL DEFAULT 0,
                is_active INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, name)
            )
        """)
        
        # Таблица расходов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                amount_from REAL NOT NULL,
                amount_to REAL NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (trip_id) REFERENCES trips(id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def create_trip(self, user_id: int, name: str, from_country: str, to_country: str,
                   from_currency: str, to_currency: str, exchange_rate: float,
                   initial_balance: float = 0) -> int:
        """Создать новое путешествие"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Деактивируем все другие путешествия пользователя
        cursor.execute("UPDATE trips SET is_active = 0 WHERE user_id = ?", (user_id,))
        
        # Создаем новое путешествие
        cursor.execute("""
            INSERT INTO trips (user_id, name, from_country, to_country, 
                            from_currency, to_currency, exchange_rate, 
                            balance_from, balance_to, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (user_id, name, from_country, to_country, from_currency, 
              to_currency, exchange_rate, initial_balance, 
              initial_balance * exchange_rate))
        
        trip_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return trip_id
    
    def get_active_trip(self, user_id: int) -> Optional[Dict]:
        """Получить активное путешествие пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM trips 
            WHERE user_id = ? AND is_active = 1
            LIMIT 1
        """, (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_trip(self, trip_id: int, user_id: int) -> Optional[Dict]:
        """Получить путешествие по ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM trips 
            WHERE id = ? AND user_id = ?
        """, (trip_id, user_id))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_all_trips(self, user_id: int) -> List[Dict]:
        """Получить все путешествия пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM trips 
            WHERE user_id = ?
            ORDER BY is_active DESC, created_at DESC
        """, (user_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def switch_active_trip(self, user_id: int, trip_id: int) -> bool:
        """Переключить активное путешествие"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Проверяем, что путешествие принадлежит пользователю
        cursor.execute("SELECT id FROM trips WHERE id = ? AND user_id = ?", 
                      (trip_id, user_id))
        if not cursor.fetchone():
            conn.close()
            return False
        
        # Деактивируем все путешествия пользователя
        cursor.execute("UPDATE trips SET is_active = 0 WHERE user_id = ?", (user_id,))
        
        # Активируем выбранное путешествие
        cursor.execute("UPDATE trips SET is_active = 1 WHERE id = ? AND user_id = ?", 
                      (trip_id, user_id))
        
        conn.commit()
        conn.close()
        return True
    
    def update_exchange_rate(self, trip_id: int, user_id: int, new_rate: float) -> bool:
        """Обновить курс обмена для путешествия"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Получаем текущий баланс
        cursor.execute("SELECT balance_from FROM trips WHERE id = ? AND user_id = ?", 
                      (trip_id, user_id))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False
        
        balance_from = row[0]
        balance_to = balance_from * new_rate
        
        # Обновляем курс и пересчитываем баланс
        cursor.execute("""
            UPDATE trips 
            SET exchange_rate = ?, balance_to = ?
            WHERE id = ? AND user_id = ?
        """, (new_rate, balance_to, trip_id, user_id))
        
        conn.commit()
        conn.close()
        return True
    
    def add_expense(self, trip_id: int, user_id: int, amount_from: float, 
                   amount_to: float, description: str = None) -> int:
        """Добавить расход"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Добавляем расход в историю
        cursor.execute("""
            INSERT INTO expenses (trip_id, user_id, amount_from, amount_to, description)
            VALUES (?, ?, ?, ?, ?)
        """, (trip_id, user_id, amount_from, amount_to, description))
        
        expense_id = cursor.lastrowid
        
        # Обновляем баланс путешествия
        cursor.execute("""
            UPDATE trips 
            SET balance_from = balance_from - ?,
                balance_to = balance_to - ?
            WHERE id = ? AND user_id = ?
        """, (amount_from, amount_to, trip_id, user_id))
        
        conn.commit()
        conn.close()
        return expense_id
    
    def get_expenses(self, trip_id: int, user_id: int, limit: int = 10) -> List[Dict]:
        """Получить историю расходов"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM expenses 
            WHERE trip_id = ? AND user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (trip_id, user_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_balance(self, trip_id: int, user_id: int) -> Optional[Tuple[float, float]]:
        """Получить баланс путешествия"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT balance_from, balance_to FROM trips 
            WHERE id = ? AND user_id = ?
        """, (trip_id, user_id))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return (row[0], row[1])
        return None

