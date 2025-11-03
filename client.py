"""
FusionMeet Client
Client application for multi-user video conferencing with audio, video, screen sharing, chat, and file transfer.
Connects to FusionMeet server and provides PyQt5-based user interface.
"""

import socket
import threading
import pickle
import struct
import time
import signal
import atexit
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QMetaObject, Qt, Q_ARG
import sys

from config import *
from gui import MainWindow
from login_dialog import LoginDialog
from chat_module import ChatHandler
from video_module import VideoHandler
from audio_module import AudioHandler
from screen_sharing_module import ScreenShareHandler
from file_sharing_module import FileSharingHandler
from utils import receive_with_size, send_with_size


class Client:
    """
    Main client class for FusionMeet.
    Manages connection to server, coordinates media handlers, and updates GUI.
    """
    
    def __init__(self):
        """Initialize client with network sockets and handler modules."""
        self.server_host = None
        self.server_port = TCP_PORT
        self.session_name = None
        self.username = None
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.is_running = False
        self.gui = None
        self.chat_handler = ChatHandler(self)
        
        # Participant tracking
        self.participants = set()  # Set of usernames
        
        # Thread management
        self.tcp_thread = None
        self.udp_thread = None
        self.heartbeat_thread = None
        
        # Media handlers (created after QApplication initialization)
        self.video_handler = None
        self.audio_handler = None
        self.screen_share_handler = None
        self.file_sharing_handler = None
        
        # Network configuration
        self.udp_port = None  # Client's UDP port for receiving
        
        # Graceful shutdown handlers
        atexit.register(self._emergency_cleanup)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle interrupt signals gracefully."""
        print(f"\n🛑 Received signal {signum}, shutting down gracefully...")
        self.stop()
        sys.exit(0)
    
    def _emergency_cleanup(self):
        """Emergency cleanup on interpreter shutdown."""
        if self.is_running:
            self.is_running = False
            try:
                if hasattr(self, 'tcp_socket'):
                    self.tcp_socket.close()
            except:
                pass
            try:
                if hasattr(self, 'udp_socket'):
                    self.udp_socket.close()
            except:
                pass
    def start(self):
        """
        Start client application and establish server connection.
        Initializes PyQt5 app, displays login dialog, and launches main GUI.
        """
        app = QApplication(sys.argv)
        
        # Apply global stylesheet for consistent dialog appearance
        app.setStyleSheet("""
        QMessageBox {
            background-color: white;
        }
        QMessageBox QLabel {
            color: black;
            font-size: 13px;
            min-width: 300px;
        }
        QMessageBox QPushButton {
            background-color: #4CAF50;
            color: white;
            padding: 6px 12px;
            border: none;
            border-radius: 4px;
            min-width: 80px;
        }
        """)
        
        # Create media handlers in main thread (required for Qt objects)
        self.video_handler = VideoHandler(self)
        self.audio_handler = AudioHandler(self)
        self.screen_share_handler = ScreenShareHandler(self)
        self.file_sharing_handler = FileSharingHandler(self)
        
        # Connection retry loop
        connected = False
        
        while not connected:
            # Show login dialog to get server IP and session credentials
            login_dialog = LoginDialog()
            result = login_dialog.exec_()
            
            # User cancelled login
            if not result:
                print("Login cancelled by user")
                return
            
            # Extract connection info
            server_ip, session_name, username = login_dialog.get_connection_info()
            if not server_ip or not username:
                continue  # Validation failed, retry
            
            # Store connection parameters
            self.server_host = server_ip
            self.session_name = session_name if session_name else "Main Session"
            self.username = username
            
            try:
                print(f"Connecting to server at {self.server_host}:{self.server_port}...")
                
                # Set connection timeout to prevent hanging
                self.tcp_socket.settimeout(5)
                
                # Attempt TCP connection to server
                self.tcp_socket.connect((self.server_host, self.server_port))
                
                # Reset timeout after successful connection
                self.tcp_socket.settimeout(None)
                
                # Bind UDP socket to random available port
                self.udp_socket.bind(('', 0))
                _, self.udp_port = self.udp_socket.getsockname()
                
                print(f"Connected to server, UDP port: {self.udp_port}")

                # Register UDP port and session info with server
                reg_msg = pickle.dumps({
                    'type': 'register_udp', 
                    'port': self.udp_port,
                    'username': self.username,
                    'session': self.session_name
                })
                send_with_size(self.tcp_socket, reg_msg)
                
                # Start heartbeat thread to maintain UDP registration
                self.heartbeat_thread = threading.Thread(target=self._send_heartbeat, daemon=False)
                self.heartbeat_thread.start()

                self.is_running = True
                connected = True

                # Start network receiver threads
                self.tcp_thread = threading.Thread(target=self.receive_tcp_data, daemon=False)
                self.udp_thread = threading.Thread(target=self.receive_udp_data, daemon=False)
                self.tcp_thread.start()
                self.udp_thread.start()

                # Initialize and display main GUI window
                self.gui = MainWindow(self, self.username)
                self.gui.show()
                
                # Display welcome message
                self.gui.add_chat_message("System", f"Welcome to {self.session_name}, {self.username}!")
                
                # Start Qt event loop
                return_code = app.exec_()
                self.stop()
                sys.exit(return_code)

            except ConnectionRefusedError:
                # Server not running or wrong IP
                msg_box = QMessageBox(None)
                msg_box.setWindowTitle("Connection Error")
                msg_box.setText("Could not connect to the server. Please check the IP address and make sure the server is running.")
                msg_box.setIcon(QMessageBox.Critical)
                msg_box.exec_()
                
                # Recreate socket for next retry
                self.tcp_socket.close()
                self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                
            except socket.timeout:
                # Connection attempt timed out
                msg_box = QMessageBox(None)
                msg_box.setWindowTitle("Connection Timeout")
                msg_box.setText("Connection to server timed out. Please check the IP address and make sure the server is running.")
                msg_box.setIcon(QMessageBox.Critical)
                msg_box.exec_()
                
                # Recreate socket for next retry
                self.tcp_socket.close()
                self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                
            except Exception as e:
                # Unexpected error during connection
                msg_box = QMessageBox(None)
                msg_box.setWindowTitle("Error")
                msg_box.setText(f"An error occurred: {str(e)}")
                msg_box.setIcon(QMessageBox.Critical)
                msg_box.exec_()
                print(f"Exception: {str(e)}")
                
                # Recreate socket for next retry
                self.tcp_socket.close()
                self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                
        # Failed to connect after all attempts
        print("Failed to connect to server after multiple attempts")
        sys.exit(1)

    def _send_heartbeat(self):
        """
        Send periodic heartbeat to maintain server connection.
        Keeps UDP registration alive and prevents timeout.
        """
        while self.is_running:
            try:
                time.sleep(15)  # Heartbeat interval: 15 seconds
                
                if not self.is_running:
                    break
                    
                # Send TCP heartbeat (reliable delivery)
                heartbeat_msg = pickle.dumps({
                    'type': 'heartbeat',
                    'username': self.username,
                    'udp_port': self.udp_port,
                    'session': self.session_name
                })
                send_with_size(self.tcp_socket, heartbeat_msg)
                
                # Send UDP heartbeat to keep NAT mapping alive
                try:
                    udp_heartbeat = pickle.dumps({
                        'type': 'heartbeat',
                        'username': self.username
                    })
                    self.udp_socket.sendto(udp_heartbeat, (self.server_host, self.server_port + 1))
                except:
                    pass  # UDP heartbeat is optional
                    
            except Exception as e:
                if self.is_running:
                    print(f"Heartbeat error: {e}")
                break

    def stop(self):
        """
        Gracefully stop client and cleanup resources.
        Stops all media streams, closes sockets, and joins threads.
        """
        print("🛑 Stopping client...")
        self.is_running = False
        
        # Stop all media handlers
        try:
            if hasattr(self, 'video_handler') and self.video_handler:
                self.video_handler.stop_stream()
        except Exception as e:
            print(f"Error stopping video handler: {e}")
            
        try:
            if hasattr(self, 'audio_handler') and self.audio_handler:
                self.audio_handler.stop_stream()
        except Exception as e:
            print(f"Error stopping audio handler: {e}")
            
        try:
            if hasattr(self, 'screen_share_handler') and self.screen_share_handler:
                self.screen_share_handler.stop_sharing()
        except Exception as e:
            print(f"Error stopping screen share handler: {e}")
        
        # Shutdown TCP socket to unblock receiver thread
        try:
            if hasattr(self, 'tcp_socket') and self.tcp_socket:
                self.tcp_socket.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass  # Socket may already be closed
        
        # Close both sockets
        try:
            if hasattr(self, 'tcp_socket') and self.tcp_socket:
                self.tcp_socket.close()
        except Exception as e:
            print(f"Error closing TCP socket: {e}")
            
            
        try:
            if hasattr(self, 'udp_socket') and self.udp_socket:
                self.udp_socket.close()
        except Exception as e:
            print(f"Error closing UDP socket: {e}")
        
        # Wait for all threads to finish (with timeout to prevent hanging)
        threads_to_join = [
            ('TCP receiver', self.tcp_thread),
            ('UDP receiver', self.udp_thread),
            ('Heartbeat', self.heartbeat_thread)
        ]
        
        for thread_name, thread in threads_to_join:
            if thread and thread.is_alive():
                print(f"⏳ Waiting for {thread_name} thread to finish...")
                thread.join(timeout=2.0)
                if thread.is_alive():
                    print(f"⚠️  {thread_name} thread did not finish in time")
                else:
                    print(f"✅ {thread_name} thread finished")
            
        print("✅ Client stopped cleanly.")

    def handle_connection_lost(self):
        """
        Handle server connection loss.
        Clears participants and notifies user via GUI.
        """
        # Clear participant list (server connection lost)
        self.participants.clear()
        
        # Update participants list in GUI
        if self.gui:
            QMetaObject.invokeMethod(
                self.gui,
                "update_participants_list",
                Qt.QueuedConnection
            )
            
            # Notify user about disconnection
            QMetaObject.invokeMethod(
                self.gui,
                "add_chat_message",
                Qt.QueuedConnection,
                Q_ARG(str, "System"),
                Q_ARG(str, "⚠️ Connection to server lost. Please restart the application.")
            )
    
    def receive_tcp_data(self):
        """
        TCP receiver thread - handles control messages and reliable data.
        Processes chat, participant lists, screen sharing, and file transfers.
        """
        reconnect_attempts = 0
        max_reconnect_attempts = 3
        
        while self.is_running:
            try:
                # Receive data with size prefix
                data = receive_with_size(self.tcp_socket)
                if not data:
                    # Connection closed by server
                    if self.is_running:
                        print("⚠️ Server closed connection")
                        
                        # Attempt to notify user
                        if reconnect_attempts < max_reconnect_attempts:
                            reconnect_attempts += 1
                            print(f"🔄 Attempting to reconnect ({reconnect_attempts}/{max_reconnect_attempts})...")
                            time.sleep(2)
                            
                            if self.gui:
                                QMetaObject.invokeMethod(
                                    self.gui,
                                    "add_chat_message",
                                    Qt.QueuedConnection,
                                    Q_ARG(str, "System"),
                                    Q_ARG(str, "Connection lost. Please restart the application.")
                                )
                    break
                
                try:
                    # Deserialize message
                    payload = pickle.loads(data)
                    msg_type = payload.get('type')
                    print(f"Received message of type: {msg_type}")
                    
                    if msg_type == 'chat':
                        # Handle chat messages and system notifications
                        try:
                            chat_data = pickle.loads(data)
                            sender = chat_data.get('sender')
                            message = chat_data.get('message', '')
                            
                            # Track participant changes from system messages
                            if sender == 'System':
                                if 'has joined the session' in message:
                                    # Extract username from join notification
                                    username = message.split(' has joined')[0]
                                    print(f"Detected user connection: {username}")
                                    if username != self.username:
                                        self.participants.add(username)
                                        
                                        # Update GUI participants list
                                        if self.gui:
                                            QMetaObject.invokeMethod(
                                                self.gui,
                                                "update_participants_list",
                                                Qt.QueuedConnection
                                            )
                                
                                elif 'left the session' in message:
                                    # Extract username from leave notification
                                    username = message.split(' has left')[0]
                                    print(f"Detected user disconnection: {username}")
                                    self.participants.discard(username)
                                    
                                    # Update GUI participants list
                                    if self.gui:
                                        QMetaObject.invokeMethod(
                                            self.gui,
                                            "update_participants_list",
                                            Qt.QueuedConnection
                                        )
                                    
                                    # Remove their video widget
                                    QMetaObject.invokeMethod(
                                        self.video_handler, 
                                        "remove_remote_video", 
                                        Qt.QueuedConnection,
                                        Q_ARG(str, username)
                                    )
                        except Exception as e:
                            print(f"Error processing system message: {str(e)}")
                            
                        # Forward to chat handler for display
                        self.chat_handler.handle_message(data)
                        
                    elif msg_type == 'video_status':
                        # Handle video streaming status updates
                        username = payload.get('username')
                        is_streaming = payload.get('is_streaming')
                        
                        # Ignore own status updates
                        if username != self.username:
                            print(f"Video status update: {username} is {'streaming' if is_streaming else 'not streaming'}")
                            self.video_handler.handle_video_status(username, is_streaming)
                    
                    elif msg_type == 'participants_list':
                        # Server sent current participants list
                        participants = payload.get('participants', [])
                        print(f"📋 Received participants list from server: {participants}")
                        
                        # Replace local participants list (don't merge)
                        self.participants.clear()
                        for username in participants:
                            if username != self.username:
                                self.participants.add(username)
                        
                        print(f"📋 Updated local participants: {sorted(self.participants)}")
                        
                        # Update GUI
                        if self.gui:
                            QMetaObject.invokeMethod(
                                self.gui,
                                "update_participants_list",
                                Qt.QueuedConnection
                            )
                    
                    elif msg_type == 'presenter_changed':
                        # Screen sharing presenter has changed
                        print(f"Received presenter_changed: {payload}")
                        self.screen_share_handler.handle_presenter_changed(payload)
                    
                    elif msg_type == 'screen_share_approved':
                        # Server approved our screen sharing request
                        print(f"Received screen_share_approved: {payload}")
                        self.screen_share_handler.handle_screen_share_approved(payload)
                    
                    elif msg_type == 'screen_share_denied':
                        # Server denied our screen sharing request
                        print(f"Received screen_share_denied: {payload}")
                        self.screen_share_handler.handle_screen_share_denied(payload)
                    
                    elif msg_type == 'screen' or msg_type == 'screen_stop':
                        # Screen sharing frame or stop notification
                        self.screen_share_handler.handle_screen_frame(data)
                    
                    elif msg_type == 'file_request':
                        # Another client requesting our shared file
                        print(f"Got file request from server, forwarding to file_sharing_handler")
                        self.file_sharing_handler.handle_file_info(data)
                        
                    elif msg_type in ['file_info', 'available_files']:
                        # File availability information
                        self.file_sharing_handler.handle_file_info(data)
                        
                    elif msg_type == 'file_chunk' or msg_type == 'file_end':
                        # File data chunk or completion notification
                        self.file_sharing_handler.handle_file_chunk(data)
                        
                    elif msg_type == 'file_error':
                        # File transfer error
                        print(f"File error: {payload.get('message', 'Unknown error')}")
                        filename = payload.get('filename', 'unknown file')
                        if hasattr(self, 'gui'):
                            self.gui.add_chat_message("System", f"File error for {filename}: {payload.get('message')}")
                            
                except (pickle.UnpicklingError, KeyError):
                    pass  # Ignore malformed messages

            except (ConnectionResetError, ConnectionAbortedError, OSError) as e:
                # TCP connection lost
                if self.is_running:
                    print(f"⚠️ TCP connection lost: {e}")
                    self.handle_connection_lost()
                break
                
            except Exception as e:
                # Unexpected error
                if self.is_running:
                    print(f"⚠️ TCP error: {e}")
                    import traceback
                    traceback.print_exc()
                break
        
        print("📡 TCP receiver thread exiting")


    def receive_udp_data(self):
        """
        UDP receiver thread - handles real-time media streams.
        Processes video frames and audio packets with minimal latency.
        """
        # Performance tracking
        frame_count = 0
        last_fps_time = time.time()
        audio_count = 0
        last_audio_time = time.time()
        
        while self.is_running:
            try:
                # Receive UDP packet (blocking call)
                data, addr = self.udp_socket.recvfrom(65536)
                
                # Check if client is shutting down
                if not self.is_running:
                    break
                    
                try:
                    # Deserialize packet
                    payload = pickle.loads(data)
                    data_type = payload.get('type')
                    username = payload.get('username', 'Unknown')
                    
                    if data_type == 'video':
                        # Video frame received
                        frame_count += 1
                        current_time = time.time()
                        
                        # Log FPS every 3 seconds
                        if current_time - last_fps_time > 3:
                            fps = frame_count / (current_time - last_fps_time)
                            print(f"Receiving video from {username} at {fps:.1f} FPS")
                            frame_count = 0
                            last_fps_time = current_time
                        
                        # Forward to video handler
                        self.video_handler.handle_frame(data, addr)
                        
                    elif data_type == 'audio' or data_type == 'mixed_audio':
                        # Audio packet received
                        audio_count += 1
                        current_time = time.time()
                        
                        # Log audio rate every 5 seconds
                        if current_time - last_audio_time > 5:
                            rate = audio_count / (current_time - last_audio_time)
                            print(f"Receiving {data_type} at {rate:.1f} packets/second")
                            audio_count = 0
                            last_audio_time = current_time
                        
                        # Forward to audio handler
                        if self.audio_handler:
                            self.audio_handler.handle_audio(data)
                        else:
                            print("No audio handler available to process audio")
                    
                except (pickle.UnpicklingError, KeyError) as e:
                    if self.is_running:
                        print(f"Error processing UDP packet: {e}")
                    
            except OSError as e:
                # Socket error (likely during shutdown)
                if self.is_running:
                    print(f"UDP socket error: {e}")
                break
                
            except Exception as e:
                # Unexpected error
                if self.is_running:
                    print(f"UDP error: {e}")
                break
        
        print("📡 UDP receiver thread exiting")


    def send_tcp(self, data):
        """
        Send data via TCP (reliable, ordered delivery).
        
        Args:
            data: Pickled data to send
        """
        try:
            send_with_size(self.tcp_socket, data)
        except OSError:
            pass  # Socket closed during shutdown

    def send_udp(self, data):
        """
        Send data via UDP (fast, unreliable delivery for real-time media).
        
        Args:
            data: Pickled data to send
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.is_running:
            return False
        
        try:
            # Ensure username is in packet for server routing
            try:
                payload = pickle.loads(data)
                if 'username' not in payload:
                    payload['username'] = self.username
                    data = pickle.dumps(payload)
            except:
                pass
            
            packet_size = len(data)
            MAX_UDP_PACKET = 8192
        
            if packet_size <= MAX_UDP_PACKET:
                # Retry logic for reliability
                max_retries = 2
                for attempt in range(max_retries):
                    try:
                        self.udp_socket.sendto(data, (self.server_host, self.server_port + 1))
                    
                        # Log video sends (reduced frequency)
                        try:
                            payload = pickle.loads(data)
                            if payload.get('type') == 'video' and attempt == 0:
                                print(f"✅ Video frame sent by {self.username}")
                        except:
                            pass
                        
                        return True
                        
                    except Exception as e:
                        if attempt == max_retries - 1:
                            print(f"❌ Failed to send UDP packet after {max_retries} attempts: {e}")
                            return False
                        time.sleep(0.001)  # Brief delay before retry
            else:
                print(f"Packet too large ({packet_size} bytes), reducing quality")
                return False
            
            return True
        
        except Exception as e:
            print(f"Error sending UDP data: {e}")
            return False


if __name__ == "__main__":
    client = Client()
    client.start()