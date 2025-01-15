import logging
import os
import time
from datetime import datetime
import threading
from pymongo import MongoClient
from pymongo.errors import PyMongoError

class MongoSyncHandler:
    def __init__(self, storage_handler=None):
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        self.db_name = os.getenv("DB_NAME", "silentscope_db")
        self.storage_handler = storage_handler
        self.sync_interval = 300  # 5 minutes
        self.client = None
        self.db = None
        self.initialize_connection()

    def initialize_connection(self):
        """Initialize MongoDB connection"""
        try:
            self.client = MongoClient(self.mongo_uri)
            self.db = self.client[self.db_name]
            logging.info("MongoDB connection initialized")
        except PyMongoError as e:
            logging.error(f"MongoDB connection error: {e}")
            raise

    def sync_data(self):
        """Sync data from local storage to MongoDB"""
        try:
            if not self.storage_handler:
                return

            # Get unprocessed records
            records = self.storage_handler.get_unprocessed_data()
            if not records:
                return

            # Process records by type
            grouped_records = {}
            record_ids = []

            for record_id, timestamp, data_type, content in records:
                if data_type not in grouped_records:
                    grouped_records[data_type] = []
                grouped_records[data_type].append({
                    'timestamp': timestamp,
                    'content': content,
                    'sync_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                record_ids.append(record_id)

            # Insert records into respective collections
            if self.db is not None:
                for data_type, type_records in grouped_records.items():
                    collection = self.db[data_type]
                    try:
                        collection.insert_many(type_records)
                    except PyMongoError as e:
                        logging.error(f"Error inserting records into MongoDB collection {data_type}: {e}")
                        raise

            # Mark records as processed
            self.storage_handler.mark_as_processed(record_ids)

            logging.info(f"Synced {len(record_ids)} records to MongoDB")

        except PyMongoError as e:
            logging.error(f"MongoDB sync error: {e}")
        except Exception as e:
            logging.error(f"General sync error: {e}")

    def start_sync(self):
        """Start periodic data synchronization"""
        while True:
            try:
                self.sync_data()
            except Exception as e:
                logging.error(f"Error in sync process: {e}")
            time.sleep(self.sync_interval)

# Create service wrapper for sync handler
class SyncService(threading.Thread):
    def __init__(self, storage_handler):
        super().__init__()
        self.storage_handler = storage_handler
        self.sync_handler = MongoSyncHandler(storage_handler)
        self.daemon = True  # Ensures the thread exits when the main program exits

    def run(self):
        """Run the sync service"""
        try:
            self.sync_handler.start_sync()
        except Exception as e:
            logging.error(f"Sync service error: {e}")
