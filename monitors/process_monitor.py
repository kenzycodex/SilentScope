import psutil
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

@dataclass
class ProcessInfo:
    """Data class for process information"""
    pid: int
    name: str
    status: str
    cpu_percent: float
    memory_percent: float
    create_time: float
    num_threads: int
    exe_path: Optional[str]
    username: Optional[str]
    timestamp: str

class ProcessMonitor:
    """Process monitoring component that integrates with the main monitoring system"""
    
    def __init__(self, storage_handler):
        self.storage_handler = storage_handler
        self.running = True
        self.previous_processes: Dict[int, ProcessInfo] = {}
        
        # Configuration
        self.sampling_interval = 3  # seconds
        self.batch_size = 100  # processes per batch
        
        # Statistics
        self.stats = {
            'processes_monitored': 0,
            'error_count': 0,
            'last_error_time': None,
            'last_batch_time': None
        }

    def get_process_info(self, pid: int) -> Optional[ProcessInfo]:
        """Get detailed information about a specific process"""
        try:
            process = psutil.Process(pid)
            with process.oneshot():  # More efficient for multiple info retrieval
                try:
                    create_time = process.create_time()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    create_time = 0
                    
                try:
                    exe_path = process.exe()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    exe_path = None
                    
                try:
                    username = process.username()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    username = None
                
                return ProcessInfo(
                    pid=process.pid,
                    name=process.name(),
                    status=process.status(),
                    cpu_percent=process.cpu_percent(interval=0.1),
                    memory_percent=process.memory_percent(),
                    create_time=create_time,
                    num_threads=process.num_threads(),
                    exe_path=exe_path,
                    username=username,
                    timestamp=datetime.now().isoformat()
                )
                
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logging.debug(f"Cannot access process {pid}: {str(e)}")
            return None
        except Exception as e:
            logging.error(f"Error getting process info for PID {pid}: {str(e)}")
            return None

    def get_system_metrics(self) -> dict:
        """Collect system-wide performance metrics"""
        try:
            return {
                'cpu_percent': psutil.cpu_percent(interval=0.1),
                'memory_percent': psutil.virtual_memory().percent,
                'swap_percent': psutil.swap_memory().percent,
                'disk_usage': {disk.mountpoint: psutil.disk_usage(disk.mountpoint).percent 
                             for disk in psutil.disk_partitions(all=False)},
                'boot_time': psutil.boot_time()
            }
        except Exception as e:
            logging.error(f"Error collecting system metrics: {str(e)}")
            return {}

    def store_process_batch(self, processes: List[ProcessInfo]):
        """Store a batch of process information"""
        try:
            batch_data = {
                'timestamp': datetime.now().isoformat(),
                'processes': [asdict(process) for process in processes if process],
                'system_metrics': self.get_system_metrics(),
                'monitor_stats': self.stats
            }
            
            self.storage_handler.store_data('process_activity', batch_data)
            self.stats['last_batch_time'] = datetime.now().isoformat()
            
        except Exception as e:
            logging.error(f"Error storing process batch: {str(e)}")
            self.stats['error_count'] += 1

    def start_monitoring(self):
        """Main monitoring loop"""
        logging.info("Starting process monitoring")
        
        try:
            while self.running:
                try:
                    current_processes = []
                    
                    # Get all running processes
                    for pid in psutil.pids():
                        process_info = self.get_process_info(pid)
                        if process_info:
                            current_processes.append(process_info)
                            self.stats['processes_monitored'] += 1
                        
                        # Store batch when reaching batch size
                        if len(current_processes) >= self.batch_size:
                            self.store_process_batch(current_processes)
                            current_processes = []
                    
                    # Store remaining processes
                    if current_processes:
                        self.store_process_batch(current_processes)
                    
                except Exception as e:
                    logging.error(f"Error in monitoring loop: {str(e)}")
                    self.stats['error_count'] += 1
                    self.stats['last_error_time'] = datetime.now().isoformat()
                
                time.sleep(self.sampling_interval)
                
        except Exception as e:
            logging.error(f"Fatal error in process monitoring: {str(e)}")
            raise
        
        finally:
            logging.info("Process monitoring stopped")

    def stop_monitoring(self):
        """Stop the monitoring process gracefully"""
        self.running = False