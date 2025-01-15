import os
import json
import logging
from datetime import datetime
import threading
from security import SecurityManager
import sqlite3
from pathlib import Path

class StorageHandler:
    def __init__(self, encryption_key=None):
        """Initialize the StorageHandler with optional encryption key"""
        self.security_manager = SecurityManager() if encryption_key is None else encryption_key
        self.db_path = Path('logs/activity.db')
        self.buffer = []
        self.buffer_lock = threading.Lock()
        self.buffer_size = 50
        self.initialize_database()

    def initialize_database(self):
        """Initialize SQLite database with necessary tables"""
        try:
            os.makedirs(self.db_path.parent, exist_ok=True)
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()

                # Create tables for different types of data
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS activity_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT,
                        type TEXT,
                        content BLOB,
                        processed BOOLEAN DEFAULT FALSE
                    )
                ''')

                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_timestamp 
                    ON activity_logs(timestamp)
                ''')

                conn.commit()
        except Exception as e:
            logging.error(f"Database initialization error: {e}")
            raise

    def store_data(self, data_type: str, content: dict):
        """Store data in buffer and database"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Encrypt the content
            encrypted_content = self.security_manager.encrypt_data(
                json.dumps(content).encode()
            )

            with self.buffer_lock:
                self.buffer.append({
                    'timestamp': timestamp,
                    'type': data_type,
                    'content': encrypted_content
                })

                # Ensure buffer is flushed when size exceeds buffer_size
                if len(self.buffer) >= self.buffer_size:
                    self._flush_buffer()

        except Exception as e:
            logging.error(f"Error storing data: {e}")

    def _flush_buffer(self):
        """Flush buffer to database"""
        try:
            with self.buffer_lock:
                if not self.buffer:
                    return

                with sqlite3.connect(str(self.db_path)) as conn:
                    cursor = conn.cursor()
                    cursor.executemany(
                        'INSERT INTO activity_logs (timestamp, type, content) VALUES (?, ?, ?)',
                        [(item['timestamp'], item['type'], item['content']) for item in self.buffer]
                    )
                    conn.commit()

                self.buffer.clear()

        except Exception as e:
            logging.error(f"Error flushing buffer: {e}")

    def get_unprocessed_data(self, limit=100):
        """Retrieve unprocessed data for syncing"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, timestamp, type, content 
                    FROM activity_logs 
                    WHERE processed = FALSE 
                    LIMIT ?
                ''', (limit,))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error retrieving unprocessed data: {e}")
            return []

    def mark_as_processed(self, record_ids):
        """Mark records as processed after successful sync"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.executemany(
                    'UPDATE activity_logs SET processed = TRUE WHERE id = ?',
                    [(id,) for id in record_ids]
                )
                conn.commit()
        except Exception as e:
            logging.error(f"Error marking records as processed: {e}")
