"""
FusionMeet Server
Handles multi-session video conferencing with N-1 audio mixing, screen sharing, and file transfer.
Manages client connections via TCP and real-time media streams via UDP.
"""

import socket
import threading
import pickle
import struct
import time
import signal
import sys
import atexit

from config import HOST, TCP_PORT, AUDIO_CHANNELS, AUDIO_RATE, AUDIO_CHUNK

from utils import send_with_size, receive_with_size
from audio_mixer import AudioMixer


class Server:
    """
    Main server class for FusionMeet video conferencing.
    Manages sessions, client connections, audio mixing, and media relay.
    """
    
    def __init__(self, host, port):
        """
        Initialize server with network sockets and data structures.
        
        Args:
            host: IP address to bind to
            port: TCP port for control channel (UDP uses port+1)
        """
        self.host = host
        self.port = port
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Client management
        self.clients = {}  # {addr: {'socket': socket, 'username': str, 'session': str}}
        self.sessions = {}  # {session_name: [client_addr1, client_addr2, ...]}
        self.udp_ports = {}  # {client_addr: udp_port}
        self.udp_endpoints = {}  # {(ip, udp_port): client_addr} for reliable UDP routing
        
        self.is_running = False
        
        # File sharing
        self.files = {}  # {filename: {'owner': addr, 'size': size, 'session': str}}
        self.available_files = {}  # {session_name: {filename: filesize}}
        
        # Audio mixing per session
        self.audio_mixers = {}  # {session_name: AudioMixer}
        
        # Audio processing thread
        self.audio_processing_thread = None
        self._audio_mix_event = threading.Event()
        
        # Screen sharing management (single presenter per session)
        self.current_presenter = {}  # {session_name: {'username': str, 'addr': tuple}}
        self.presenter_lock = threading.Lock()
        
        # Thread tracking for clean shutdown
        self.accept_thread = None
        self.udp_thread = None
        
        # Register cleanup handlers for graceful shutdown
        atexit.register(self._emergency_cleanup)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """
        Handle interrupt signals (SIGINT/SIGTERM) for graceful shutdown.
        
        Args:
            signum: Signal number received
            frame: Current stack frame
        """
        print(f"\n🛑 Received signal {signum}, shutting down gracefully...")
        self.stop()
        sys.exit(0)
    
    def _emergency_cleanup(self):
        """
        Emergency cleanup handler for interpreter shutdown.
        Closes sockets to release system resources.
        """
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
        Start the server and begin accepting connections.
        Initializes TCP and UDP sockets, starts worker threads.
        """
        # Allow socket reuse to prevent "Address already in use" errors
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        self.tcp_socket.bind((self.host, self.port))
        self.tcp_socket.listen(5)
        self.udp_socket.bind((self.host, self.port + 1))
        self.is_running = True
        print(f"Server started on {self.host}:{self.port}")

        try:
            # Start worker threads (non-daemon for clean shutdown)
            self.accept_thread = threading.Thread(target=self.accept_connections, daemon=False)
            self.udp_thread = threading.Thread(target=self.receive_udp_data, daemon=False)
            
            self.accept_thread.start()
            self.udp_thread.start()
            
            # Start N-1 audio mixer thread
            self.audio_processing_thread = threading.Thread(
                target=self.process_audio,
                name="audio-mixer",
                daemon=False
            )
            self.audio_processing_thread.start()
            
            # Keep main thread alive
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Received Ctrl+C, shutting down...")
            self.stop()
        finally:
            if self.is_running:
                self.stop()

    def stop(self):
        """
        Gracefully shutdown server and cleanup all resources.
        Waits for threads to finish and closes all connections.
        """
        print("🛑 Stopping server...")
        self.is_running = False
        
        # Signal audio mixer to exit
        self._audio_mix_event.set()
        if self.audio_processing_thread and self.audio_processing_thread.is_alive():
            print("⏳ Waiting for audio mixer thread to finish...")
            self.audio_processing_thread.join(timeout=1.0)
        
        self.audio_mixers.clear()
        
        # Close all client connections (use list() for thread-safe iteration)
        print("🔌 Closing client connections...")
        for client_data in list(self.clients.values()):
            try:
                client_data['socket'].close()
            except Exception:
                pass
        
        # Close server sockets (unblocks accept() and recvfrom() calls)
        try:
            self.tcp_socket.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        
        try:
            self.tcp_socket.close()
        except Exception:
            pass
            
        try:
            self.udp_socket.close()
        except Exception:
            pass
        
        # Wait for worker threads to finish
        threads_to_join = [
            ('TCP accept', self.accept_thread),
            ('UDP receiver', self.udp_thread)
        ]
        
        for thread_name, thread in threads_to_join:
            if thread and thread.is_alive():
                print(f"⏳ Waiting for {thread_name} thread to finish...")
                thread.join(timeout=2.0)
                if thread.is_alive():
                    print(f"⚠️  {thread_name} thread did not finish in time")
                else:
                    print(f"✅ {thread_name} thread finished")
            
        print("✅ Server stopped cleanly.")

    def remove_client(self, client_addr):
        """
        Remove client and cleanup all associated resources.
        Updates participants list immediately for remaining users.
        
        Args:
            client_addr: TCP address tuple (ip, port) of client to remove
        """
        if client_addr in self.clients:
            username = self.clients[client_addr].get('username', 'Unknown')
            session = self.clients[client_addr].get('session')
            
            print(f"🧹 Removing client {username} from {client_addr}")
            
            # Remove from session and update all participants
            if session and session in self.sessions:
                if client_addr in self.sessions[session]:
                    self.sessions[session].remove(client_addr)
                
                # Update participants list for all remaining clients
                for remaining_addr in list(self.sessions[session]):
                    if remaining_addr in self.clients:
                        self.send_participants_list(remaining_addr, session)
                
                # Cleanup empty sessions
                if not self.sessions[session]:
                    self.audio_mixers.pop(session, None)
                    del self.sessions[session]
            
            # Release presenter role if owned by this client
            with self.presenter_lock:
                if session in self.current_presenter:
                    if self.current_presenter[session]['addr'] == client_addr:
                        del self.current_presenter[session]
                        print(f"🛑 {username} was presenting - released presenter role")
            
            # Cleanup UDP port mappings
            if client_addr in self.udp_ports:
                udp_port = self.udp_ports[client_addr]
                self.udp_endpoints.pop((client_addr[0], udp_port), None)
                del self.udp_ports[client_addr]
            
            # Cleanup shared files from this client
            files_to_remove = []
            for filename, file_info in self.files.items():
                if file_info['owner'] == client_addr:
                    files_to_remove.append(filename)
                    session = file_info['session']
                    if session in self.available_files and filename in self.available_files[session]:
                        del self.available_files[session][filename]
            
            for filename in files_to_remove:
                del self.files[filename]
            
            # Remove client entry and close socket
            if client_addr in self.clients:
                try:
                    self.clients[client_addr]['socket'].close()
                except:
                    pass
                del self.clients[client_addr]

    def accept_connections(self):
        """
        Accept incoming TCP connections in a loop.
        Spawns new thread for each client connection.
        """
        while self.is_running:
            try:
                client_socket, addr = self.tcp_socket.accept()
                print(f"New connection from {addr}")
                threading.Thread(target=self.handle_client, args=(client_socket, addr), daemon=True).start()
            except OSError as e:
                # Socket closed during shutdown (expected)
                if self.is_running:
                    print(f"Accept error: {e}")
                break
            except Exception as e:
                if self.is_running:
                    print(f"Unexpected error in accept_connections: {e}")
                break
        
        print("📡 TCP accept thread exiting")

    def handle_client(self, client_socket, addr):
        """
        Handle individual client connection and process messages.
        Manages registration, file sharing, screen sharing, and chat.
        
        Args:
            client_socket: TCP socket for this client
            addr: Client address tuple (ip, port)
        """
        try:
            # Initialize client entry
            self.clients[addr] = {
                'socket': client_socket, 
                'username': None, 
                'session': None
            }
            
            while self.is_running:
                data = receive_with_size(client_socket)
                if not data:
                    break
                    
                # Deserialize message
                try:
                    payload = pickle.loads(data)
                    msg_type = payload.get('type')
                    
                except (pickle.UnpicklingError, AttributeError, EOFError, KeyError) as e:
                    # Skip corrupted packets silently
                    continue
                except Exception as e:
                    if self.is_running:
                        print(f"⚠️ Error unpacking data from {addr}: {e}")
                    continue
                
                try:
                    # Handle video streaming status updates
                    if msg_type == 'video_status':
                        username = payload.get('username')
                        is_streaming = payload.get('is_streaming')
                        
                        # Validate sender identity
                        if addr in self.clients and self.clients[addr].get('username') == username:
                            session = self.clients[addr]['session']
                            print(f"Video status from {username}: {'streaming' if is_streaming else 'stopped'}")
                            
                            # Broadcast status to session
                            self.broadcast_tcp(data, addr, session)
                        else:
                            print(f"Invalid video status update from {addr}")
                        
                        continue
                        
                    elif msg_type == 'screen_stop':
                        # Handle presenter stopping screen share
                        username = payload.get('username')
                        
                        if addr in self.clients:
                            session = self.clients[addr]['session']
                            print(f"Screen sharing stopped by {username}")
                            
                            # Broadcast stop to all viewers
                            self.broadcast_tcp(data, addr, session)
                            
                            self.broadcast_system_message(
                                f"{username} has stopped sharing their screen", 
                                session
                            )
                        
                        continue
                    
                    elif msg_type == 'register_udp':
                        # Handle client registration with session and UDP port
                        udp_port = payload.get('port')
                        username = payload.get('username', f"User-{addr[0]}:{addr[1]}")
                        session = payload.get('session', 'Main Session')
                        
                        self.clients[addr]['username'] = username
                        self.clients[addr]['session'] = session
                        
                        # Dynamic UDP port update (handles port changes)
                        previous_port = self.udp_ports.get(addr)
                        if previous_port is not None and previous_port != udp_port:
                            print(f"🔄 Client {username} changed UDP port from {previous_port} to {udp_port}")
                            self.udp_endpoints.pop((addr[0], previous_port), None)
                        
                        self.udp_ports[addr] = udp_port
                        self.udp_endpoints[(addr[0], udp_port)] = addr
                        
                        # Add to session
                        if session not in self.sessions:
                            self.sessions[session] = []
                        if addr not in self.sessions[session]:
                            self.sessions[session].append(addr)
                        
                        print(f"Client {username} registered in session '{session}' from {addr} (UDP port: {udp_port})")
                        
                        self.send_participants_list(addr, session)
                        
                        # Notify session about new user
                        self.broadcast_system_message(
                            f"{username} has joined the session", 
                            session,
                            exclude_addr=None
                        )
                        
                        # Update participants list for all clients
                        for client_addr in self.sessions[session]:
                            if client_addr in self.clients:
                                self.send_participants_list(client_addr, session)
                        
                        self.send_available_files(addr, session)
                        
                        continue
                    
                    elif msg_type == 'heartbeat':
                        # Client keepalive with optional UDP port update

                        if 'udp_port' in payload:
                            new_udp_port = payload['udp_port']
                            current_udp_port = self.udp_ports.get(addr)
                            
                            # Update if port changed
                            if current_udp_port != new_udp_port:
                                print(f"🔄 Client {self.clients[addr].get('username')} updated UDP port to {new_udp_port}")
                                if current_udp_port:
                                    self.udp_endpoints.pop((addr[0], current_udp_port), None)
                                self.udp_ports[addr] = new_udp_port
                                self.udp_endpoints[(addr[0], new_udp_port)] = addr
                        
                        continue
                    
                    elif msg_type == 'file_info':
                        # Store uploaded file metadata for session
                        filename = payload.get('filename')
                        filesize = payload.get('filesize')
                        session = self.clients[addr]['session']
                        sender_username = self.clients[addr]['username']
                        
                        print(f"Server received file_info: {filename}, {filesize} bytes from {sender_username}")
                        
                        self.files[filename] = {
                            'owner': addr,
                            'size': filesize,
                            'session': session,
                            'sender': sender_username
                        }
                        
                        # Add to session's file list
                        if session not in self.available_files:
                            self.available_files[session] = {}
                        self.available_files[session][filename] = filesize
                        
                        # Include sender in broadcast
                        if 'sender' not in payload:
                            payload['sender'] = sender_username
                            data = pickle.dumps(payload)
                        
                        print(f"Broadcasting file info to all clients in session {session}")
                        
                    elif msg_type == 'file_request':
                        # Route download request to file owner
                        filename = payload.get('filename')
                        session = self.clients[addr]['session']
                        
                        # Verify file exists in session
                        if session not in self.available_files or filename not in self.available_files[session]:
                            print(f"File {filename} requested but not available in session {session}")
                            error_msg = {
                                'type': 'file_error',
                                'message': f"File {filename} is not available",
                                'filename': filename
                            }
                            send_with_size(client_socket, pickle.dumps(error_msg))
                            continue
                            
                        # Verify file metadata exists
                        if filename not in self.files:
                            print(f"File {filename} is in available_files but missing from files dictionary")
                            error_msg = {
                                'type': 'file_error',
                                'message': f"File information is incomplete",
                                'filename': filename
                            }
                            send_with_size(client_socket, pickle.dumps(error_msg))
                            continue
                            
                        file_info = self.files[filename]
                        owner = file_info['owner']
                        
                        # Forward request to owner
                        if owner in self.clients:
                            print(f"Forwarding file request from {addr} for {filename} to {owner}")
                            payload['requester'] = addr
                            forward_data = pickle.dumps(payload)
                            send_with_size(self.clients[owner]['socket'], forward_data)
                        else:
                            # Owner disconnected
                            print(f"File owner for {filename} is no longer connected")
                            error_msg = {
                                'type': 'file_error',
                                'message': f"File owner is no longer connected",
                                'filename': filename
                            }
                            send_with_size(client_socket, pickle.dumps(error_msg))
                            
                            # Cleanup orphaned file
                            if session in self.available_files and filename in self.available_files[session]:
                                del self.available_files[session][filename]
                                if filename in self.files:
                                    del self.files[filename]
                        continue
                        
                    elif msg_type == 'file_chunk' or msg_type == 'file_end':
                        # Route file data chunks to requester
                        filename = payload.get('filename')
                        requester = payload.get('requester')
                        
                        print(f"Received {msg_type} for {filename} from {addr}" + 
                              (f" for requester {requester}" if requester else ""))
                        
                        # Initial upload (no requester)
                        if requester is None:
                            for filename_info in self.files:
                                if filename_info == filename:
                                    if msg_type == 'file_end':
                                        print(f"File {filename} uploaded successfully from {addr}")
                                    continue
                        elif requester in self.clients:
                            # Forward chunk to downloader
                            forward_socket = self.clients[requester]['socket']
                            print(f"Forwarding {msg_type} for {filename} to requester {requester}")
                            send_with_size(forward_socket, data)
                            
                            if msg_type == 'file_end':
                                print(f"File {filename} download completed for {requester}")
                        else:
                            print(f"Cannot forward file chunk: requester {requester} not found")
                            
                        continue
                    
                    elif msg_type == 'screen_share_request':
                        # Handle presenter role request/release
                        self.handle_screen_share_request(addr, payload)
                        continue
                    
                    elif msg_type == 'screen':
                        # Only broadcast screen frames from active presenter
                        session = self.clients[addr]['session']
                        with self.presenter_lock:
                            presenter_info = self.current_presenter.get(session, {})
                            if presenter_info.get('addr') == addr:
                                self.broadcast_tcp(data, addr, session)
                            else:
                                username = self.clients[addr].get('username', 'Unknown')
                                print(f"Ignoring screen frame from non-presenter {username}")
                        continue
                    
                    # Broadcast other messages to session
                    if addr in self.clients and self.clients[addr].get('session'):
                        self.broadcast_tcp(data, addr, self.clients[addr]['session'])
                    
                except (pickle.UnpicklingError, KeyError, AttributeError) as e:
                    pass
                except Exception as e:
                    if self.is_running:
                        print(f"⚠️ Error processing message from {addr}: {e}")
                    
        except (ConnectionResetError, ConnectionAbortedError, OSError) as e:
            # Normal disconnect - handle gracefully
            username = self.clients.get(addr, {}).get('username', 'Unknown')
            session = self.clients.get(addr, {}).get('session')
            
            if username and session:
                print(f"🔌 Connection lost with {username} ({addr})")
                
                # Notify before removal
                if session in self.sessions:
                    self.broadcast_system_message(
                        f"{username} has left the session", 
                        session,
                        exclude_addr=addr
                    )
                
                # Remove client and update participants
                self.remove_client(addr)
                
                # Update remaining clients
                if session in self.sessions:
                    for remaining_addr in self.sessions[session]:
                        if remaining_addr in self.clients:
                            self.send_participants_list(remaining_addr, session)
            else:
                self.remove_client(addr)
                    
        finally:
            # Ensure cleanup
            if addr in self.clients:
                self.remove_client(addr)
            
    def broadcast_system_message(self, message, session, exclude_addr=None):
        """
        Send system message to all clients in session.
        
        Args:
            message: Message text to send
            session: Target session name
            exclude_addr: Optional address to skip
        """
        system_msg = pickle.dumps({
            'type': 'chat',
            'sender': 'System',
            'message': message,
            'timestamp': time.time()
        })
        
        if session in self.sessions:
            for addr in self.sessions[session]:
                if addr != exclude_addr and addr in self.clients:
                    try:
                        client_data = self.clients[addr]
                        send_with_size(client_data['socket'], system_msg)
                    except OSError:
                        continue

    def receive_udp_data(self):
        """
        Receive and route UDP packets (video/audio streams).
        Implements dynamic endpoint learning for NAT traversal.
        """
        print("📡 UDP receiver thread started")
    
        while self.is_running:
            try:
                data, udp_addr = self.udp_socket.recvfrom(65536)

                if not self.is_running:
                    break

                udp_key = (udp_addr[0], udp_addr[1])
                sender_addr = self.udp_endpoints.get(udp_key)

                # Dynamic endpoint learning (extract username from packet)
                if sender_addr is None:
                    username = None
                    try:
                        payload = pickle.loads(data)
                        username = payload.get('username')
                    except:
                        pass
                
                    if username:
                        # Find client by username
                        matching_clients = []
                        for addr, client_info in self.clients.items():
                            if client_info.get('username') == username:
                                matching_clients.append(addr)
                        
                        if matching_clients:
                            sender_addr = matching_clients[0]
                            print(f"🔍 LEARNED UDP: {udp_addr} -> {username} at {sender_addr}")
                            self.udp_endpoints[udp_key] = sender_addr
                            self.udp_ports[sender_addr] = udp_addr[1]
                        else:
                            print(f"📨 No active client found for username: {username}")
                            continue
                    else:
                        print(f"📨 Received UDP from unknown endpoint {udp_addr} (no username)")
                        continue

                if sender_addr not in self.clients:
                    print(f"UDP sender {sender_addr} not in client list")
                    continue

                try:
                    payload = pickle.loads(data)
                except Exception as exc:
                    print(f"Failed to unpack UDP payload from {sender_addr}: {exc}")
                    continue

                data_type = payload.get('type')

                # Route audio to N-1 mixer
                if data_type == 'audio':
                    session = self.clients[sender_addr].get('session')
                    username = payload.get('username') or self.clients[sender_addr].get('username')
                    
                    # Extract audio frame (support both formats)
                    frame = None
                    if 'raw_data' in payload:
                        # Legacy format with prefix
                        raw_data = payload['raw_data']
                        try:
                            parts = raw_data.split(b'|', 1)
                            if len(parts) >= 2 and parts[0] == b'a':
                                frame = parts[1]
                        except Exception as e:
                            pass
                    else:
                        frame = payload.get('frame')

                    if not session or frame is None:
                        continue

                    # Add to session's N-1 audio mixer
                    mixer = self.audio_mixers.setdefault(
                        session,
                        AudioMixer(
                            channels=AUDIO_CHANNELS,
                            sample_rate=AUDIO_RATE,
                            chunk_size=AUDIO_CHUNK,
                        ),
                    )
                    mixer.add_frame(username or 'Unknown', frame)
                    
                elif data_type == 'video':
                    # Relay video frames to session
                    username = payload.get('username', 'Unknown')
                    print(f"📹 Server received video from {username} ({len(data)} bytes)")
                    self.broadcast_udp(data, sender_addr, payload)
                    
                else:
                    self.broadcast_udp(data, sender_addr, payload)
                
            except Exception as e:
                # Never crash UDP thread - log and continue
                if self.is_running:
                    print(f"⚠️ UDP receiver error (recovering): {e}")
                continue
        
        print("📡 UDP receiver thread exiting")

    def broadcast_tcp(self, data, sender_addr, session=None):
        """
        Broadcast TCP message to session members.
        
        Args:
            data: Serialized message data
            sender_addr: Address of sender (excluded from broadcast)
            session: Target session (None = all clients)
        """
        # Determine target list
        targets = []
        if session and session in self.sessions:
            targets = [addr for addr in self.sessions[session] if addr in self.clients]
        else:
            targets = list(self.clients.keys())
        
        # Track disconnected clients
        failed_clients = []
            
        for addr in targets:
            if addr != sender_addr:
                try:
                    client_data = self.clients.get(addr)
                    if client_data and 'socket' in client_data:
                        send_with_size(client_data['socket'], data)
                except (OSError, ConnectionResetError, BrokenPipeError) as e:
                    failed_clients.append(addr)
                    if self.is_running:
                        print(f"⚠️ Failed to send to {addr}: {e}")
                except Exception as e:
                    if self.is_running:
                        print(f"⚠️ Unexpected broadcast error to {addr}: {e}")
                    failed_clients.append(addr)
        
        # Cleanup disconnected clients
        for addr in failed_clients:
            if addr in self.clients:
                print(f"🧹 Removing disconnected client {addr}")
                threading.Thread(target=self.remove_client, args=(addr,), daemon=True).start()

    def broadcast_udp(self, data, sender_addr, payload=None):
        """
        Broadcast UDP packet to session members.
        
        Args:
            data: Raw UDP packet data
            sender_addr: Sender's TCP address (excluded from broadcast)
            payload: Optional pre-parsed packet (avoids re-parsing)
        """
        if sender_addr not in self.clients:
            print(f"Ignoring UDP data from unknown sender {sender_addr}")
            return
        
        sender_info = self.clients[sender_addr]
        session = sender_info.get('session')
        sender_username = sender_info.get('username', 'Unknown')
    
        if not session or session not in self.sessions:
            print(f"No valid session for {sender_username}, not broadcasting")
            return
    
        # Parse payload if needed
        if payload is None:
            try:
                payload = pickle.loads(data)
            except Exception as exc:
                print(f"Error decoding UDP payload for broadcast: {exc}")
                return

        packet_type = payload.get('type', 'unknown')
    
        # Build target list (exclude sender and clients without UDP)
        targets = []
        for addr in self.sessions[session]:
            client_username = self.clients[addr].get('username', 'Unknown')
        
            # Skip sender or same username (prevent echo)
            if addr == sender_addr or client_username == sender_username:
                continue
            
            # Skip if no UDP port registered
            if addr not in self.udp_ports:
                continue
            
            targets.append(addr)
        
        if not targets:
            print(f"No targets for {packet_type} from {sender_username} in session {session}")
            return
        
        # Send to all targets
        successful = 0
        failed_targets = []
        
        for addr in targets:
            try:
                udp_port = self.udp_ports[addr]
            
                self.udp_socket.sendto(data, (addr[0], udp_port))
                successful += 1
            except Exception as e:
                failed_targets.append((addr, str(e)))
                print(f"Error sending to {addr}: {e}")
            
        # Log results
        if packet_type == 'video' and successful > 0:
            print(f"📹 Video from {sender_username} forwarded to {successful}/{len(targets)} clients in session {session}")
            if failed_targets:
                print(f"⚠️ Failed to send to {len(failed_targets)} clients: {failed_targets}")
    
    def process_audio(self):
        """
        Process N-1 audio mixing for all sessions.
        Each client receives mixed audio excluding their own voice.
        Runs at 50Hz (20ms intervals) for smooth audio delivery.
        """
        print("🔊 Starting audio processing thread with N-1 mixing")
        
        mix_interval = 0.02  # 20ms processing interval
        
        while self.is_running and not self._audio_mix_event.is_set():
            loop_started = time.time()
            try:
                # Process each session's audio
                for session_name, mixer in list(self.audio_mixers.items()):
                    # Verify session still exists
                    if session_name not in self.sessions:
                        del self.audio_mixers[session_name]
                        continue
                        
                    clients_in_session = self.sessions[session_name]
                    
                    if not clients_in_session:
                        continue
                        
                    # N-1 mixing: personalized mix for each client
                    for client_addr in clients_in_session:
                        if client_addr not in self.clients or client_addr not in self.udp_ports:
                            continue
                            
                        client_username = self.clients[client_addr].get('username', 'Unknown')
                        
                        # Mix all audio except this client's (prevents echo)
                        mixed_frame = mixer.get_mixed_frame_n_minus_1(client_username)
                        
                        # Send only if non-silent
                        if mixed_frame and mixed_frame.strip(b"\x00"):
                            audio_packet = pickle.dumps({
                                'type': 'audio',
                                'username': 'SERVER_MIX',
                                'raw_data': b'a|' + mixed_frame,
                                'frame': mixed_frame
                            })
                            
                            try:
                                udp_port = self.udp_ports[client_addr]
                                self.udp_socket.sendto(audio_packet, (client_addr[0], udp_port))
                            except Exception as e:
                                pass
                
                # Sleep with interrupt capability
                elapsed = time.time() - loop_started
                remaining = max(0.0, mix_interval - elapsed)
                if self._audio_mix_event.wait(remaining):
                    break
                
            except Exception as e:
                print(f"Error in audio processing thread: {e}")
                if self._audio_mix_event.wait(1.0):
                    break
        
        print("🔊 Audio processing thread exiting")
    
    def send_available_files(self, client_addr, session_name):
        """
        Send list of available files to client.
        
        Args:
            client_addr: Target client address
            session_name: Session to get files from
        """
        if client_addr not in self.clients:
            return
            
        client_socket = self.clients[client_addr]['socket']
        
        if session_name in self.available_files and self.available_files[session_name]:
            files_msg = {
                'type': 'available_files',
                'files': self.available_files[session_name]
            }
            
            try:
                print(f"Sending {len(self.available_files[session_name])} available files to new client {client_addr}")
                send_with_size(client_socket, pickle.dumps(files_msg))
            except Exception as e:
                print(f"Failed to send available files to client {client_addr}: {e}")
        else:
            print(f"No files available for session {session_name}")
    
    def send_participants_list(self, client_addr, session_name):
        """
        Send current participants list to client.
        
        Args:
            client_addr: Target client address
            session_name: Session to get participants from
        """
        if client_addr not in self.clients:
            return
            
        client_socket = self.clients[client_addr]['socket']
        
        # Collect all participant usernames in session
        participants = []
        if session_name in self.sessions:
            for addr in self.sessions[session_name]:
                if addr in self.clients and 'username' in self.clients[addr]:
                    username = self.clients[addr]['username']
                    if username:
                        participants.append(username)
        
        participants_msg = {
            'type': 'participants_list',
            'participants': participants
        }
        
        try:
            print(f"📋 Sending participants list to {self.clients[client_addr].get('username')}: {participants}")
            send_with_size(client_socket, pickle.dumps(participants_msg))
        except Exception as e:
            print(f"Failed to send participants list to client {client_addr}: {e}")
    
    def handle_screen_share_request(self, client_addr, payload):
        """
        Handle screen sharing presenter role requests.
        Enforces single presenter per session.
        
        Args:
            client_addr: Requesting client address
            payload: Request data with action (start/stop)
        """
        session = self.clients.get(client_addr, {}).get('session')
        username = self.clients.get(client_addr, {}).get('username')
        action = payload.get('action')
        
        if not session or not username:
            print(f"Invalid screen share request from {client_addr}")
            return
        
        with self.presenter_lock:
            if action == 'start':
                # Check if presenter already exists
                if session in self.current_presenter:
                    current = self.current_presenter[session]
                    # Deny - another user is presenting
                    try:
                        response = {
                            'type': 'screen_share_denied',
                            'reason': f'{current["username"]} is currently presenting',
                            'current_presenter': current['username']
                        }
                        send_with_size(
                            self.clients[client_addr]['socket'],
                            pickle.dumps(response)
                        )
                        print(f"❌ Denied screen share request from {username} - {current['username']} is presenting")
                    except Exception as e:
                        print(f"Error sending denial to {client_addr}: {e}")
                    return
                
                # Grant presenter role
                self.current_presenter[session] = {
                    'username': username,
                    'addr': client_addr
                }
                
                print(f"✅ {username} is now presenting in session {session}")
                
                # Notify all session members
                presenter_update = {
                    'type': 'presenter_changed',
                    'presenter': username,
                    'is_presenting': True
                }
                self.broadcast_tcp_to_session(session, presenter_update)
                
                # Confirm to requester
                try:
                    confirmation = {
                        'type': 'screen_share_approved',
                        'message': 'You are now presenting'
                    }
                    send_with_size(
                        self.clients[client_addr]['socket'],
                        pickle.dumps(confirmation)
                    )
                except Exception as e:
                    print(f"Error sending approval to {client_addr}: {e}")
            
            elif action == 'stop':
                # Release presenter role
                if session in self.current_presenter:
                    if self.current_presenter[session]['addr'] == client_addr:
                        del self.current_presenter[session]
                        
                        print(f"🛑 {username} stopped presenting in session {session}")
                        
                        # Notify session that presentation ended
                        presenter_update = {
                            'type': 'presenter_changed',
                            'presenter': None,
                            'is_presenting': False
                        }
                        self.broadcast_tcp_to_session(session, presenter_update)
    
    def broadcast_tcp_to_session(self, session, message):
        """
        Broadcast message to all clients in session.
        
        Args:
            session: Target session name
            message: Dict message to serialize and send
        """
        if session not in self.sessions:
            return
        
        serialized = pickle.dumps(message)
        for addr in list(self.sessions[session]):
            if addr in self.clients:
                try:
                    send_with_size(self.clients[addr]['socket'], serialized)
                except Exception as e:
                    print(f"Error broadcasting to {addr}: {e}")

    def sync_all_participants_lists(self):
        """
        Sync participants lists for all sessions.
        Useful for periodic refresh or after network issues.
        """
        for session_name in list(self.sessions.keys()):
            for client_addr in list(self.sessions[session_name]):
                if client_addr in self.clients:
                    self.send_participants_list(client_addr, session_name)

if __name__ == "__main__":
    server = Server(HOST, TCP_PORT)
    server.start()