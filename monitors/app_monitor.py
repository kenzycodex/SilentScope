import os
import logging
import win32gui
import win32process
import psutil
import time
from datetime import datetime
from typing import Dict, Optional, Set
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass
class WindowInfo:
    """Data class for window information"""
    window_title: str
    process_name: str
    process_path: str
    process_id: int
    memory_usage: float  # in MB
    cpu_percent: float
    timestamp: str
    window_handle: int

class AppMonitor:
    """Enhanced application monitoring system"""

    def __init__(self, storage_handler):
        self.storage_handler = storage_handler
        self.last_active_window: Optional[str] = None
        self.active_apps: Set[str] = set()
        self.running = True
        
        # Configuration
        self.check_interval = 1.0  # seconds
        self.summary_interval = 3600  # 1 hour in seconds
        self.last_summary_time = datetime.now()
        
        # Statistics
        self.stats = {
            'windows_monitored': 0,
            'errors': 0,
            'last_error_time': None,
            'last_summary_time': None
        }

    def get_process_performance(self, process: psutil.Process) -> Dict[str, float]:
        """Get process performance metrics"""
        try:
            with process.oneshot():  # More efficient for multiple info retrieval
                return {
                    'memory_mb': process.memory_info().rss / 1024 / 1024,
                    'cpu_percent': process.cpu_percent(interval=0.1)
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {'memory_mb': 0.0, 'cpu_percent': 0.0}

    def get_active_window_info(self) -> Optional[WindowInfo]:
        """Get detailed information about the currently active window"""
        try:
            window_handle = win32gui.GetForegroundWindow()
            if not window_handle:
                return None

            window_title = win32gui.GetWindowText(window_handle)
            if not window_title.strip():  # Skip empty window titles
                return None
                
            # Get process information
            _, process_id = win32process.GetWindowThreadProcessId(window_handle)
            
            try:
                process = psutil.Process(process_id)
                perf_metrics = self.get_process_performance(process)
                
                # Get executable path safely
                try:
                    process_path = process.exe()
                except (psutil.AccessDenied, FileNotFoundError):
                    process_path = "Access Denied"

                return WindowInfo(
                    window_title=window_title,
                    process_name=process.name(),
                    process_path=str(Path(process_path)),
                    process_id=process_id,
                    memory_usage=perf_metrics['memory_mb'],
                    cpu_percent=perf_metrics['cpu_percent'],
                    timestamp=datetime.now().isoformat(),
                    window_handle=window_handle
                )

            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logging.debug(f"Process access error: {str(e)}")
                return None

        except Exception as e:
            self.stats['errors'] += 1
            self.stats['last_error_time'] = datetime.now().isoformat()
            logging.error(f"Error getting active window info: {str(e)}")
            return None

    def store_window_change(self, window_info: WindowInfo):
        """Store window change event with additional context"""
        try:
            window_data = asdict(window_info)
            window_data['monitor_stats'] = self.stats
            
            self.storage_handler.store_data("active_window", window_data)
            self.stats['windows_monitored'] += 1
            
        except Exception as e:
            logging.error(f"Error storing window change: {str(e)}")
            self.stats['errors'] += 1

    def generate_app_summary(self):
        """Generate and store detailed application usage summary"""
        try:
            current_time = datetime.now()
            
            # Calculate time since last summary
            time_diff = (current_time - self.last_summary_time).total_seconds()
            
            summary = {
                "timestamp": current_time.isoformat(),
                "period_seconds": time_diff,
                "active_apps_count": len(self.active_apps),
                "active_apps_list": sorted(list(self.active_apps)),
                "monitor_stats": self.stats,
                "system_stats": {
                    "cpu_percent": psutil.cpu_percent(interval=0.1),
                    "memory_percent": psutil.virtual_memory().percent,
                    "system_uptime": int(time.time() - psutil.boot_time())
                }
            }
            
            self.storage_handler.store_data("app_summary", summary)
            self.active_apps.clear()
            self.last_summary_time = current_time
            self.stats['last_summary_time'] = current_time.isoformat()
            
        except Exception as e:
            logging.error(f"Error generating app summary: {str(e)}")
            self.stats['errors'] += 1

    def start_monitoring(self):
        """Start the application monitoring process"""
        logging.info("Starting application monitoring")
        self.last_summary_time = datetime.now()
        
        try:
            while self.running:
                try:
                    current_window = self.get_active_window_info()
                    
                    if current_window:
                        # Check if window has changed
                        if (not self.last_active_window or 
                            current_window.window_title != self.last_active_window):
                            
                            self.last_active_window = current_window.window_title
                            self.active_apps.add(current_window.process_name)
                            self.store_window_change(current_window)
                        
                        # Check if it's time for summary
                        current_time = datetime.now()
                        if (current_time - self.last_summary_time).total_seconds() >= self.summary_interval:
                            self.generate_app_summary()
                    
                except Exception as e:
                    logging.error(f"Error in monitoring loop: {str(e)}")
                    self.stats['errors'] += 1
                    
                time.sleep(self.check_interval)
                
        except Exception as e:
            logging.error(f"Fatal error in app monitoring: {str(e)}")
            raise
        
        finally:
            logging.info("Application monitoring stopped")

    def stop_monitoring(self):
        """Stop the monitoring process gracefully"""
        self.running = False
        # Generate final summary before stopping
        self.generate_app_summary()