import psutil
import time
import logging
from datetime import datetime
import threading
import win32serviceutil
import win32service
import win32event
import servicemanager
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict

# Data class to hold the connection information
@dataclass
class ConnectionInfo:
    """Data class for connection information"""
    local_address: Optional[str]
    remote_address: Optional[str]
    status: str
    pid: int
    process_name: Optional[str]
    timestamp: str

class NetworkMonitor:
    """Network monitoring component that integrates with the main monitoring system"""
    
    def __init__(self, storage_handler):
        self.storage_handler = storage_handler
        self.connection_history: Dict[str, ConnectionInfo] = {}
        self.running = True
        
        # Configure monitoring parameters
        self.sampling_interval = 5  # seconds
        self.batch_size = 50  # number of records to store at once
        
        # Monitoring statistics
        self.stats = {
            'connections_monitored': 0,
            'last_error_time': None,
            'error_count': 0,
            'last_batch_time': None
        }

    def get_connection_info(self) -> List[ConnectionInfo]:
        """Collect current network connection information"""
        connections = []
        try:
            for conn in psutil.net_connections(kind='all'):
                try:
                    process = psutil.Process(conn.pid) if conn.pid else None
                    
                    local_addr = (f"{conn.laddr.ip}:{conn.laddr.port}" 
                                if conn.laddr and hasattr(conn.laddr, 'ip') 
                                else None)
                    remote_addr = (f"{conn.raddr.ip}:{conn.raddr.port}" 
                                 if conn.raddr and hasattr(conn.raddr, 'ip') 
                                 else None)
                    
                    connection_info = ConnectionInfo(
                        local_address=local_addr,
                        remote_address=remote_addr,
                        status=conn.status,
                        pid=conn.pid if conn.pid is not None else -1,
                        process_name=process.name() if process else None,
                        timestamp=datetime.now().isoformat()
                    )
                    connections.append(connection_info)
                    
                except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError) as e:
                    logging.debug(f"Skipping connection due to: {str(e)}")
                    continue
                    
        except Exception as e:
            self.stats['last_error_time'] = datetime.now()
            self.stats['error_count'] += 1
            logging.error(f"Error collecting connection info: {str(e)}")
            
        return connections

    def _get_network_stats(self) -> dict:
        """Collect network interface statistics"""
        try:
            net_io = psutil.net_io_counters()
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv,
                "errin": net_io.errin,
                "errout": net_io.errout,
                "dropin": net_io.dropin,
                "dropout": net_io.dropout
            }
        except Exception as e:
            logging.error(f"Error collecting network stats: {str(e)}")
            return {}

    def _store_batch(self, connections: List[ConnectionInfo]):
        """Store a batch of connection data"""
        try:
            batch_data = {
                "timestamp": datetime.now().isoformat(),
                "connections": [asdict(conn) for conn in connections],
                "network_stats": self._get_network_stats(),
                "monitor_stats": self.stats
            }
            
            self.storage_handler.store_data("network_activity", batch_data)
            self.stats['last_batch_time'] = datetime.now()
            
        except Exception as e:
            logging.error(f"Error storing network data batch: {str(e)}")
            self.stats['error_count'] += 1

    def monitor_connections(self):
        """Monitor and log network connections"""
        while self.running:
            try:
                current_connections = self.get_connection_info()
                
                # Update statistics
                self.stats['connections_monitored'] += len(current_connections)
                
                # Store the batch
                self._store_batch(current_connections)
                
            except Exception as e:
                logging.error(f"Error monitoring connections: {e}")
                self.stats['error_count'] += 1
                
            # Wait for the next sampling interval
            time.sleep(self.sampling_interval)

    def start_monitoring(self):
        """Start network monitoring in a separate thread"""
        threading.Thread(target=self.monitor_connections, daemon=True).start()

    def stop_monitoring(self):
        """Stop the monitoring process"""
        self.running = False


class NetworkMonitorService(win32serviceutil.ServiceFramework):
    """Windows service wrapper for network monitor"""
    _svc_name_ = "NetworkMonitorService"
    _svc_display_name_ = "Network Activity Monitor"
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.monitor = None

    def SvcStop(self):
        """Stop the service"""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        """Run the service"""
        try:
            from data_handlers.storage_handler import StorageHandler
            encryption_key = "your_encryption_key_here"  # Replace with your actual encryption key
            storage_handler = StorageHandler(encryption_key=encryption_key)
            self.monitor = NetworkMonitor(storage_handler)
            self.monitor.start_monitoring()
            
            # Wait until stop event is triggered
            win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)
            
        except Exception as e:
            logging.error(f"Service error: {e}")
            self.SvcStop()
