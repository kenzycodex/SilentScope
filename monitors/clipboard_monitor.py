import win32clipboard
import win32con
import time
import logging
import hashlib
from datetime import datetime
import threading
import pythoncom
from typing import Dict, Any, Optional
import queue

class ClipboardMonitor:
    def __init__(self, storage_handler, check_interval: float = 1.0):
        """
        Initialize the ClipboardMonitor.
        
        Args:
            storage_handler: Handler for storing clipboard data
            check_interval: How often to check for clipboard changes (in seconds)
        """
        self.storage_handler = storage_handler
        self.check_interval = check_interval
        self.last_hash = None
        self.running = False
        self.monitor_thread = None
        self.data_queue = queue.Queue()
        
        # Define supported clipboard formats
        self.supported_formats = [
            (win32con.CF_TEXT, 'text'),
            (win32con.CF_UNICODETEXT, 'unicode_text'),
            (win32con.CF_HDROP, 'file_list'),
            (win32con.CF_DIB, 'image'),
            (win32con.CF_BITMAP, 'bitmap')
        ]
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def get_clipboard_data(self) -> Optional[Dict[str, Any]]:
        """
        Get data from clipboard with support for multiple formats.
        
        Returns:
            Dictionary containing clipboard data by format, or None if error occurs
        """
        try:
            pythoncom.CoInitialize()
            win32clipboard.OpenClipboard()
            clipboard_data = {}

            for format_id, format_name in self.supported_formats:
                try:
                    if win32clipboard.IsClipboardFormatAvailable(format_id):
                        data = self._get_format_data(format_id, format_name)
                        if data is not None:
                            clipboard_data[format_name] = data
                except Exception as e:
                    self.logger.error(f"Error reading clipboard format {format_name}: {str(e)}")

            return clipboard_data if clipboard_data else None

        except Exception as e:
            self.logger.error(f"Error accessing clipboard: {str(e)}")
            return None
        finally:
            try:
                win32clipboard.CloseClipboard()
            except:
                pass
            pythoncom.CoUninitialize()

    def _get_format_data(self, format_id: int, format_name: str) -> Optional[Any]:
        """
        Get clipboard data for a specific format.
        
        Args:
            format_id: Windows clipboard format identifier
            format_name: Human-readable format name
            
        Returns:
            Clipboard data in the specified format, or None if unavailable
        """
        try:
            if format_id in [win32con.CF_TEXT, win32con.CF_UNICODETEXT]:
                data = win32clipboard.GetClipboardData(format_id)
                return data.decode('utf-8', errors='ignore') if isinstance(data, bytes) else data
                
            elif format_id == win32con.CF_HDROP:
                return list(win32clipboard.GetClipboardData(format_id))
                
            elif format_id in [win32con.CF_DIB, win32con.CF_BITMAP]:
                return "[Image Data Present]"
                
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting {format_name} data: {str(e)}")
            return None

    def calculate_hash(self, data: Dict[str, Any]) -> str:
        """Calculate hash of clipboard data"""
        return hashlib.md5(str(data).encode()).hexdigest()

    def _monitor_clipboard(self):
        """Internal method to monitor clipboard changes"""
        while self.running:
            try:
                clipboard_data = self.get_clipboard_data()
                
                if clipboard_data:
                    current_hash = self.calculate_hash(clipboard_data)
                    
                    if current_hash != self.last_hash:
                        self.last_hash = current_hash
                        self.data_queue.put({
                            "timestamp": datetime.now().isoformat(),
                            "content": clipboard_data
                        })
                        
            except Exception as e:
                self.logger.error(f"Error in clipboard monitoring: {str(e)}")
                
            time.sleep(self.check_interval)

    def _process_queue(self):
        """Process queued clipboard data"""
        while self.running:
            try:
                while not self.data_queue.empty():
                    data = self.data_queue.get_nowait()
                    self.storage_handler.store_data("clipboard", data)
                    self.data_queue.task_done()
            except Exception as e:
                self.logger.error(f"Error processing queue: {str(e)}")
            time.sleep(0.1)

    def start_monitoring(self):
        """Start clipboard monitoring"""
        if not self.running:
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitor_clipboard)
            self.process_thread = threading.Thread(target=self._process_queue)
            
            self.monitor_thread.daemon = True
            self.process_thread.daemon = True
            
            self.monitor_thread.start()
            self.process_thread.start()
            
            self.logger.info("Clipboard monitoring started")

    def stop_monitoring(self):
        """Stop clipboard monitoring"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join()
        if self.process_thread:
            self.process_thread.join()
        self.logger.info("Clipboard monitoring stopped")