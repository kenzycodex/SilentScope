import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import logging

class SecurityManager:
    def __init__(self):
        # Load environment variables from .env file
        load_dotenv()
        
        # Generate or load encryption key
        self.encryption_key = self._load_or_generate_key()
        
        # Initialize the cipher with the encryption key
        self.cipher = Fernet(self.encryption_key)

    def _load_or_generate_key(self) -> bytes:
        """Load existing key from environment or generate a new one"""
        key = os.getenv('FERNET_KEY')
        if not key:
            key = Fernet.generate_key()
            self._save_key_to_env(key)
        return key.encode() if isinstance(key, str) else key

    def _save_key_to_env(self, key: bytes):
        """Save encryption key to .env file securely"""
        # Check if the key is already in the .env file to prevent duplicates
        if 'FERNET_KEY' not in open('.env').read():
            with open('.env', 'a') as f:
                f.write(f'\nFERNET_KEY={key.decode()}')
        else:
            logging.warning("Encryption key already exists in .env file")

    def encrypt_data(self, data: bytes) -> bytes:
        """Encrypt data using Fernet encryption"""
        try:
            return self.cipher.encrypt(data)
        except Exception as e:
            logging.error(f"Encryption error: {e}")
            raise

    def decrypt_data(self, encrypted_data: bytes) -> bytes:
        """Decrypt data using Fernet encryption"""
        try:
            return self.cipher.decrypt(encrypted_data)
        except Exception as e:
            logging.error(f"Decryption error: {e}")
            raise

def load_encryption_key():
    """Initialize SecurityManager and return encryption key"""
    security_manager = SecurityManager()
    return security_manager.encryption_key
