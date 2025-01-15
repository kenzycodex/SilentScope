import os
import logging
import json
from datetime import datetime
import ctypes
from pathlib import Path
from typing import Union, Dict, Any, List, Optional
import platform
import hashlib
import re
import socket
from functools import wraps
import traceback
import sys
from logging.handlers import RotatingFileHandler

class SystemUtils:
    """Central class for system utility functions"""
    
    @staticmethod
    def get_system_info() -> Dict[str, str]:
        """Get detailed system information"""
        return {
            'platform': platform.platform(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'python_version': sys.version,
            'hostname': socket.gethostname(),
            'username': os.getenv('USERNAME', os.getenv('USER', 'unknown'))
        }

class LogConfig:
    """Advanced logging configuration"""
    
    DEFAULT_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s'
    
    def __init__(self, log_dir: str = 'logs'):
        self.log_dir = Path(log_dir)
        self.log_levels = {
            'system': logging.INFO,
            'error': logging.ERROR,
            'debug': logging.DEBUG,
            'security': logging.WARNING
        }
        
    def setup_logging(self, enable_console: bool = True):
        """Configure comprehensive logging system"""
        try:
            # Ensure log directory exists
            self.log_dir.mkdir(parents=True, exist_ok=True)
            
            # Create base logger
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.DEBUG)
            
            # Clear any existing handlers
            root_logger.handlers.clear()
            
            # Create formatters
            standard_formatter = logging.Formatter(self.DEFAULT_FORMAT)
            detailed_formatter = logging.Formatter(
                self.DEFAULT_FORMAT + '\nStack Trace: %(stack_trace)s'
            )
            
            # Add handlers for different log types
            handlers = self._create_handlers(standard_formatter, detailed_formatter)
            
            # Add console handler if enabled
            if enable_console:
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(standard_formatter)
                console_handler.setLevel(logging.INFO)
                handlers.append(console_handler)
            
            # Add all handlers to root logger
            for handler in handlers:
                root_logger.addHandler(handler)
                
            logging.info("Logging system initialized successfully")
            
        except Exception as e:
            print(f"Failed to initialize logging: {str(e)}")
            raise
    
    def _create_handlers(self, standard_formatter, detailed_formatter) -> List[logging.Handler]:
        """Create and configure log handlers"""
        handlers = []
        
        # Create rotating file handlers for each log level
        log_files = {
            'system': 'system.log',
            'error': 'error.log',
            'debug': 'debug.log',
            'security': 'security.log'
        }
        
        for log_type, filename in log_files.items():
            handler = self._create_rotating_handler(
                self.log_dir / filename,
                self.log_levels[log_type],
                detailed_formatter if log_type == 'error' else standard_formatter
            )
            handlers.append(handler)
            
        return handlers
    
    @staticmethod
    def _create_rotating_handler(
        filepath: Path,
        level: int,
        formatter: logging.Formatter,
        max_bytes: int = 10485760,  # 10MB
        backup_count: int = 5
    ) -> logging.Handler:
        """Create a rotating file handler"""
        handler = RotatingFileHandler(
            str(filepath),
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        handler.setLevel(level)
        handler.setFormatter(formatter)
        return handler

class SecurityUtils:
    """Security utility functions"""
    
    @staticmethod
    def hash_data(data: Union[str, bytes]) -> str:
        """Create secure hash of data"""
        if isinstance(data, str):
            data = data.encode()
        return hashlib.blake2b(data).hexdigest()
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent path traversal"""
        return re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    
    @staticmethod
    def sanitize_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize sensitive data with advanced pattern matching"""
        if not isinstance(data, dict):
            return data
            
        sanitized = data.copy()
        sensitive_patterns = [
            r'password',
            r'token',
            r'key',
            r'secret',
            r'auth',
            r'credential',
            r'api[_-]?key',
            r'access[_-]?token'
        ]
        
        pattern = re.compile('|'.join(sensitive_patterns), re.IGNORECASE)
        
        def _sanitize_value(value: Any) -> Any:
            if isinstance(value, dict):
                return SecurityUtils.sanitize_data(value)
            elif isinstance(value, list):
                return [_sanitize_value(v) for v in value]
            return value
        
        for key, value in sanitized.items():
            if pattern.search(key):
                sanitized[key] = '[REDACTED]'
            else:
                sanitized[key] = _sanitize_value(value)
        
        return sanitized

class FileSystemUtils:
    """File system utility functions"""
    
    @staticmethod
    def ensure_hidden_folder(folder_path: Union[str, Path], hide: bool = True) -> Path:
        """Create and optionally hide a folder"""
        folder_path = Path(folder_path)
        
        try:
            folder_path.mkdir(parents=True, exist_ok=True)
            
            if hide and platform.system() == 'Windows':
                ctypes.windll.kernel32.SetFileAttributesW(str(folder_path), 0x02)
            elif hide and platform.system() in ['Linux', 'Darwin']:
                if not folder_path.name.startswith('.'):
                    new_path = folder_path.parent / f'.{folder_path.name}'
                    folder_path.rename(new_path)
                    folder_path = new_path
                    
            return folder_path
            
        except Exception as e:
            logging.error(f"Failed to create/hide folder {folder_path}: {str(e)}")
            raise

class TimeUtils:
    """Time-related utility functions"""
    
    @staticmethod
    def format_timestamp(microseconds: bool = True) -> str:
        """Return formatted timestamp"""
        format_string = "%Y-%m-%d %H:%M:%S.%f" if microseconds else "%Y-%m-%d %H:%M:%S"
        return datetime.now().strftime(format_string)
    
    @staticmethod
    def parse_timestamp(timestamp: str) -> datetime:
        """Parse timestamp string to datetime object"""
        try:
            return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")

def error_handler(func):
    """Decorator for consistent error handling"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_msg = f"Error in {func.__name__}: {str(e)}"
            if logging.getLogger().handlers:
                logging.error(error_msg, extra={'stack_trace': traceback.format_exc()})
            else:
                print(error_msg)
                print(traceback.format_exc())
            raise
    return wrapper

# Initialize logging system
def initialize_logging(log_dir: str = 'logs', enable_console: bool = True):
    """Initialize the logging system"""
    log_config = LogConfig(log_dir)
    log_config.setup_logging(enable_console)

# Initialize utilities
def initialize_utils(log_dir: str = 'logs') -> None:
    """Initialize all utility systems"""
    try:
        # Create and hide logs directory
        FileSystemUtils.ensure_hidden_folder(log_dir)
        
        # Initialize logging
        initialize_logging(log_dir)
        
        # Log system information
        system_info = SystemUtils.get_system_info()
        logging.info(f"System initialized - Environment: {json.dumps(system_info)}")
        
    except Exception as e:
        print(f"Failed to initialize utilities: {str(e)}")
        raise