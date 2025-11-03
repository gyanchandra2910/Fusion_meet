"""
Video Module for FusionMeet

Handles webcam capture, video streaming, and multi-user display.
Features:
- 320x240 resolution, JPEG compression (50% quality)
- UDP transmission for low latency
- 3x3 grid supporting up to 9 participants
- Thread-safe signal/slot architecture
"""

import cv2
import pickle
import struct
import threading
import numpy as np
import time
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QMetaObject, Q_ARG, Qt
from PyQt5.QtCore import QCoreApplication, pyqtSlot

from config import *


class VideoWidget(QWidget):
    """
    Display widget for individual video stream.
    Shows video with username label, thread-safe GUI updates.
    """
    
    # PyQt signals for thread-safe UI updates
    set_frame_signal = pyqtSignal(object)
    set_label_signal = pyqtSignal(str)
    clear_frame_signal = pyqtSignal()
    
    def __init__(self, parent=None):
        """
        Initialize video widget.
        
        Args:
            parent: Parent Qt widget
        """
        super().__init__(parent)
        self.setMinimumSize(320, 240)
        self.setMaximumSize(640, 480)
        
        # Layout configuration
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Video display label
        self.frame_label = QLabel(self)
        self.frame_label.setAlignment(Qt.AlignCenter)
        self.frame_label.setMinimumSize(320, 240)
        
        # Username label (overlay at bottom)
        self.name_label = QLabel("User", self)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setStyleSheet("background-color: rgba(0, 0, 0, 150); color: white; padding: 2px;")
        self.name_label.setMaximumHeight(20)
        
        # Add widgets to layout
        main_layout.addWidget(self.frame_label, 1)
        main_layout.addWidget(self.name_label, 0)
        
        self.setLayout(main_layout)
        self.setStyleSheet("border: 2px solid #333333;")
        
        # Connect signals to slots for thread-safe updates
        self.set_frame_signal.connect(self._set_frame_slot)
        self.set_label_signal.connect(self._set_label_slot)
        self.clear_frame_signal.connect(self._clear_frame_slot)
        
        # Default to black frame
        self.clear_frame()

    def set_label(self, username):
        """
        Set username displayed on video widget.
        
        Args:
            username: Name to display (thread-safe via signal)
        """
        self.set_label_signal.emit(username)
        
    @pyqtSlot(str)
    def _set_label_slot(self, username):
        """Update username label in GUI thread."""
        self.name_label.setText(username)

    def clear_frame(self):
        """Display black placeholder when no video available."""
        self.clear_frame_signal.emit()
        
    @pyqtSlot()
    def _clear_frame_slot(self):
        """Set black frame in GUI thread."""
        black_frame = QPixmap(320, 240)
        black_frame.fill(Qt.black)
        self.frame_label.setPixmap(black_frame)
        
    def set_frame(self, frame):
        """
        Display video frame in widget.
        
        Args:
            frame: OpenCV BGR numpy array or None (thread-safe)
        """
        if frame is not None:
            frame_copy = frame.copy()  # Avoid threading issues
            self.set_frame_signal.emit(frame_copy)
        else:
            self.clear_frame_signal.emit()
            
    @pyqtSlot(object)
    def _set_frame_slot(self, frame):
        """
        Update video frame in GUI thread.
        Converts OpenCV BGR to Qt QPixmap for display.
        
        Args:
            frame: OpenCV BGR numpy array
        """
        try:
            if frame is None or frame.size == 0:
                print("⚠️ Received empty frame, showing black")
                self._clear_frame_slot()
                return
                
            # Resize to 320x240
            resized_frame = cv2.resize(frame, (320, 240))
            
            # Validate dimensions
            if resized_frame.shape[0] <= 0 or resized_frame.shape[1] <= 0 or resized_frame.shape[2] != 3:
                print(f"❌ Invalid frame dimensions: {resized_frame.shape}")
                self._clear_frame_slot()
                return
            
            # Convert BGR to RGB for Qt
            try:
                # Ensure contiguous memory for QImage
                if not resized_frame.flags['C_CONTIGUOUS']:
                    resized_frame = np.ascontiguousarray(resized_frame)
                
                # Create QImage and convert to QPixmap
                image = QImage(resized_frame.data, resized_frame.shape[1], resized_frame.shape[0], 
                            resized_frame.strides[0], QImage.Format_RGB888).rgbSwapped()
                pixmap = QPixmap.fromImage(image)
                
                self.frame_label.setPixmap(pixmap)
                self.frame_label.setScaledContents(False)
            except Exception as e:
                print(f"💥 Error creating QImage/QPixmap: {str(e)}")
                self._clear_frame_slot()
        except Exception as e:
            print(f"💥 Error setting frame: {str(e)}")
            self._clear_frame_slot()


class VideoHandler(QObject):
    """
    Manages video capture, streaming, and multi-user display.
    Handles webcam capture, transmission, remote video reception, and 3x3 grid layout.
    """
    
    # PyQt signals for thread-safe GUI operations
    add_video_widget_signal = pyqtSignal(QWidget, int, int)
    remove_video_widget_signal = pyqtSignal(QWidget)
    update_frame_signal = pyqtSignal(QWidget, object)
    create_widget_signal = pyqtSignal(str)
    participants_changed_signal = pyqtSignal()
    
    def __init__(self, client):
        """
        Initialize video handler.
        
        Args:
            client: Client instance for network communication
        """
        super().__init__()
        self.client = client
        self.is_streaming = False
        self.video_capture = None
        
        # Video widgets management
        self.local_video_widget = None
        self.remote_video_widgets = {}  # username -> VideoWidget
        
        # Address to username mapping for incoming frames
        self.addr_to_username = {}  # (ip, port) -> username
        
        # Frame cache for widgets being created
        self.pending_frames = {}  # username -> frame (temporary storage)
        self._pending_lock = threading.Lock()  # Thread-safe cache access
        
        # Grid layout tracking
        self.positions = {}  # (row, col) -> username
        
        # Performance tracking
        self.last_fps_time = 0
        self.frame_count = 0
        
        # Connect signals to slots for thread-safe GUI updates
        self.add_video_widget_signal.connect(self._add_video_widget_slot)
        self.remove_video_widget_signal.connect(self._remove_video_widget_slot)
        self.update_frame_signal.connect(self._update_frame_slot)
        self.create_widget_signal.connect(self._create_remote_video_widget_slot)
        
        print("Video handler initialized")
        
    @pyqtSlot(QWidget, int, int)
    def _add_video_widget_slot(self, widget, row, col):
        """Add video widget to grid in GUI thread."""
        if widget and self.client and self.client.gui:
            self.client.gui.add_video_widget(widget, row, col)
        
    @pyqtSlot(QWidget)
    def _remove_video_widget_slot(self, widget):
        """Remove video widget from layout in GUI thread."""
        if widget and self.client and self.client.gui:
            self.client.gui.remove_video_widget(widget)
        
    @pyqtSlot(QWidget, object)
    def _update_frame_slot(self, widget, frame):
        """Update video frame in widget (GUI thread)."""
        if widget and frame is not None:
            widget.set_frame(frame)
        else:
            print(f"⚠️ Cannot update frame - widget: {widget is not None}, frame: {frame is not None}")

    def start_stream(self):
        """
        Start webcam capture and video streaming.
        Tries multiple camera indices to find working camera.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        if self.is_streaming:
            print("Already streaming")
            return
            
        print("Starting video stream...")
        
        # Try camera indices 0-4 to find working camera
        working_camera = None
        for idx in range(5):
            test_cap = cv2.VideoCapture(idx)
            if test_cap.isOpened():
                ret, test_frame = test_cap.read()
                if ret and test_frame is not None and test_frame.size > 0:
                    working_camera = idx
                    test_cap.release()
                    print(f"✅ Found working camera at index {idx}")
                    break
                test_cap.release()
            time.sleep(0.1)
        
        if working_camera is None:
            print("❌ No working camera found! Tried indices 0-4")
            return False
        
        # Configure camera settings
        self.video_capture = cv2.VideoCapture(working_camera)
        self.video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.video_capture.set(cv2.CAP_PROP_FPS, 30)
        
        if not self.video_capture.isOpened():
            print(f"❌ Failed to open camera {working_camera}")
            return False

        try:
            # Create local video widget
            if not self.local_video_widget:
                self.local_video_widget = VideoWidget()
                self.local_video_widget.set_label(f"{self.client.username} (You)")
                
            # Reserve top-left corner for local video
            self.positions[(0, 0)] = self.client.username
            
            # Add to GUI grid
            self.add_video_widget_signal.emit(self.local_video_widget, 0, 0)
            print(f"Local video added at position 0,0")
            
            # Start capture timer (must be in GUI thread)
            self.stream_timer = QTimer()
            self.stream_timer.timeout.connect(self.capture_and_send)
            self.stream_timer.start(1000 // VIDEO_FPS)
            
            self.is_streaming = True
            
            # Notify other clients
            self.send_status_update(True)
            
            print("Video streaming started successfully")
            return True
            
        except Exception as e:
            print(f"Error starting video stream: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def stop_stream(self):
        """
        Stop webcam capture and video streaming.
        Releases camera and notifies other clients.
        """
        if not self.is_streaming:
            return
            
        print("Stopping video stream...")
        self.is_streaming = False
        
        try:
            # Stop capture timer
            if hasattr(self, 'stream_timer'):
                self.stream_timer.stop()
                self.stream_timer = None
            
            # Release webcam
            if self.video_capture:
                self.video_capture.release()
                self.video_capture = None
            
            # Clear local video display
            if self.local_video_widget:
                self.local_video_widget.clear_frame()
            
            # Notify other clients
            self.send_status_update(False)
            
            print("Video stream stopped")
            
        except Exception as e:
            print(f"Error stopping video stream: {str(e)}")
            import traceback
            traceback.print_exc()

    def capture_and_send(self):
        """
        Capture frame from webcam and send to other clients.
        Compresses to JPEG at 50% quality, sends via UDP.
        Local preview shows mirrored (selfie mode).
        """
        if not self.is_streaming or not self.video_capture:
            return
            
        try:
            # Capture frame
            ret, frame = self.video_capture.read()
            if not ret:
                return
            
            # Validate frame
            if frame is None or frame.size == 0:
                return
            
            # Display local preview with mirror effect
            if self.local_video_widget:
                preview_frame = cv2.flip(frame, 1)
                self.local_video_widget.set_frame(preview_frame)
            
            # Compression settings
            JPEG_QUALITY = 50
            FRAME_WIDTH = 320
            FRAME_HEIGHT = 240
            MAX_VIDEO_PACKET = 65507  # UDP safe maximum
            
            # Resize for transmission
            frame_resized = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))
            
            # JPEG compression
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
            ret, compressed_frame = cv2.imencode('.jpg', frame_resized, encode_param)
            
            if not ret:
                return
            
            # Check packet size limit
            if len(compressed_frame.tobytes()) > MAX_VIDEO_PACKET:
                return
                
            # Create packet
            data = pickle.dumps({
                'type': 'video',
                'username': self.client.username,
                'frame': compressed_frame.tobytes(),
                'q': JPEG_QUALITY,
                'r': (FRAME_WIDTH, FRAME_HEIGHT),
                'timestamp': time.time()
            })
            
            # Send via UDP
            self.client.send_udp(data)
                
        except Exception as e:
            if self.is_streaming:
                pass  # Silent - errors common during camera ops
                    
        except Exception as e:
            print(f"Error sending video frame: {str(e)}")
    
    def send_status_update(self, is_streaming):
        """
        Notify server of video streaming status change.
        
        Args:
            is_streaming: True if started, False if stopped
        """
        try:
            data = pickle.dumps({
                'type': 'video_status',
                'username': self.client.username,
                'is_streaming': is_streaming
            })
            
            # Send via TCP (reliable)
            self.client.send_tcp(data)
            print(f"Video status sent: {'streaming' if is_streaming else 'stopped'}")
        except Exception as e:
            print(f"Error sending video status: {str(e)}")
    
    @pyqtSlot(str, bool)
    def handle_video_status(self, username, is_streaming):
        """
        Handle video status update from another client.
        
        Args:
            username: User whose status changed
            is_streaming: True if started, False if stopped
        """
        print(f"Video status update: {username} is {'streaming' if is_streaming else 'not streaming'}")
        
        self.process_video_status(username, is_streaming)
        
    def process_video_status(self, username, is_streaming):
        """
        Process video status change in GUI thread.
        
        Args:
            username: User whose status changed
            is_streaming: True if started, False if stopped
        """
        try:
            # User stopped streaming - clear their frame
            if not is_streaming and username in self.remote_video_widgets:
                print(f"Clearing video for {username} who stopped streaming")
                # Clear frame if real widget exists
                if self.remote_video_widgets[username] != "creating":
                    self.remote_video_widgets[username].clear_frame()
                
            # User started streaming - create widget if needed
            elif is_streaming and username not in self.remote_video_widgets:
                print(f"Creating placeholder for {username} who started streaming")
                self.remote_video_widgets[username] = "creating"
                self.create_widget_signal.emit(username)
                
        except Exception as e:
            print(f"Error processing video status: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def remove_remote_video(self, username):
        """
        Remove disconnected user's video widget.
        
        Args:
            username: User who disconnected
        """
        print(f"Removing video for disconnected user: {username}")
        
        if username not in self.remote_video_widgets:
            return
            
        # Find grid position
        position_to_remove = None
        for pos, user in self.positions.items():
            if user == username:
                position_to_remove = pos
                break
        
        if position_to_remove:
            del self.positions[position_to_remove]
        
        # Remove widget from GUI
        widget = self.remote_video_widgets[username]
        self.client.gui.remove_video_widget(widget)
        widget.deleteLater()
        del self.remote_video_widgets[username]
        
        # Reorganize grid to fill gaps
        self.reorganize_grid()
        
    def reorganize_grid(self):
        """
        Reorganize video grid to fill empty positions.
        Moves videos to optimal positions (top-left priority).
        """
        if not self.remote_video_widgets:
            return
            
        try:
            # Find available positions (skip 0,0 for local video)
            available_positions = []
            for row in range(3):
                for col in range(3):
                    if row == 0 and col == 0:
                        continue
                    if (row, col) not in self.positions:
                        available_positions.append((row, col))
            
            # Move videos to better positions (top-left priority)
            for row in range(2, -1, -1):
                for col in range(2, -1, -1):
                    pos = (row, col)
                    
                    if row == 0 and col == 0:
                        continue
                        
                    if pos not in self.positions:
                        continue
                        
                    # Move to better position if available
                    if available_positions and available_positions[0] < pos:
                        username = self.positions[pos]
                        widget = self.remote_video_widgets[username]
                        
                        # Remove from current position
                        self.client.gui.remove_video_widget(widget)
                        del self.positions[pos]
                        
                        # Add to new position
                        new_pos = available_positions.pop(0)
                        self.positions[new_pos] = username
                        new_row, new_col = new_pos
                        self.client.gui.add_video_widget(widget, new_row, new_col)
                        print(f"Moved {username} from {pos} to {new_pos}")
                        
                        # Old position now available
                        available_positions.append(pos)
                        available_positions.sort()
        except Exception as e:
            print(f"Error reorganizing grid: {str(e)}")
            import traceback
            traceback.print_exc()

    def handle_frame(self, data, addr):
        """
        Process incoming video frame from remote client.
        Decodes JPEG, creates widget if needed, displays frame.
        
        Args:
            data: Pickled video packet
            addr: Sender's network address
        """
        try:
            # Deserialize packet
            payload = pickle.loads(data)
            if payload['type'] != 'video':
                return
                
            username = payload.get('username', 'Unknown')
            
            # Ignore our own frames (server echo)
            if username == self.client.username:
                return
                
            # Map address to username
            self.addr_to_username[addr] = username
            
            self.participants_changed_signal.emit()
            
            # Decode compressed frame
            frame_data = payload.get('frame')
            if not frame_data:
                return
            
            # JPEG decompression
            try:
                frame_np = np.frombuffer(frame_data, dtype=np.uint8)
                frame = cv2.imdecode(frame_np, cv2.IMREAD_COLOR)
                
                if frame is None or frame.size == 0:
                    return
                    
            except Exception:
                return
            
            # Create widget for new user (in GUI thread)
            if username not in self.remote_video_widgets:
                self.remote_video_widgets[username] = "creating"
                # Cache frame while widget is being created
                with self._pending_lock:
                    self.pending_frames[username] = frame
                
                self.create_widget_signal.emit(username)
            elif self.remote_video_widgets[username] == "creating":
                # Update cached frame (keep latest)
                with self._pending_lock:
                    self.pending_frames[username] = frame
            else:
                # Display in existing widget
                widget = self.remote_video_widgets[username]
                self.update_frame_signal.emit(widget, frame)
            
        except pickle.UnpicklingError:
            pass  # Ignore corrupted packets
        except Exception:
            pass  # Silent fail - expected with UDP
            
    @pyqtSlot(str)
    def _create_remote_video_widget_slot(self, username):
        """
        Create video widget for remote user in GUI thread.
        
        Args:
            username: User to create widget for
        """
        try:
            print(f"🏗️ _create_remote_video_widget_slot called for {username}")
            
            # Check if widget already exists
            if username in self.remote_video_widgets and isinstance(self.remote_video_widgets[username], VideoWidget):
                print(f"⚠️ Widget for {username} already exists as real widget")
                # Apply cached frame if available
                widget = self.remote_video_widgets[username]
                with self._pending_lock:
                    pending = self.pending_frames.pop(username, None)
                if pending is not None:
                    self.update_frame_signal.emit(widget, pending)
                return
                
            print(f"🎨 Creating video widget for {username} in main thread")
            widget = VideoWidget()
            widget.set_label(username)
            
            # Find grid position
            position = self.get_next_position()
            if position:
                row, col = position
                print(f"📍 Adding widget to grid at position {row},{col}")
                
                # Store widget before adding to GUI (prevent race conditions)
                self.remote_video_widgets[username] = widget
                self.positions[position] = username
                
                # Add to GUI
                self.client.gui.add_video_widget(widget, row, col)
                
                print(f"✅ Successfully added {username}'s video at position {row},{col}")
                
                # Apply cached frame immediately
                with self._pending_lock:
                    pending = self.pending_frames.pop(username, None)
                if pending is not None:
                    print(f"🖼️ Applying pending frame to new widget for {username}")
                    self.update_frame_signal.emit(widget, pending)
            else:
                print(f"❌ No available position for {username}'s video")
                # Cleanup
                if username in self.remote_video_widgets:
                    del self.remote_video_widgets[username]
                    
        except Exception as e:
            print(f"💥 Error creating video widget for {username}: {str(e)}")
            import traceback
            traceback.print_exc()
            # Cleanup on error
            if username in self.remote_video_widgets:
                del self.remote_video_widgets[username]
            
    def get_next_position(self):
        """
        Find next available position in 3x3 video grid.
        
        Returns:
            tuple: (row, col) position or None if grid full
        """
        # 3x3 grid for up to 9 participants
        for row in range(3):
            for col in range(3):
                # Position 0,0 reserved for local video
                if row == 0 and col == 0:
                    continue
                
                if (row, col) not in self.positions:
                    return (row, col)
                    
        print("Warning: No available positions in video grid")
        return None
            
    @pyqtSlot(str)
    def remove_remote_video(self, username):
        """
        Remove remote user's video (slot for signal).
        
        Args:
            username: User to remove
        """
        print(f"Removing video for disconnected user: {username}")
        
        self.process_remove_remote_video(username)
            
    def process_remove_remote_video(self, username):
        """
        Process video removal in GUI thread.
        
        Args:
            username: User whose video to remove
        """
        try:
            print(f"Processing removal of {username}'s video on main thread")
            
            # Find user's grid position
            position_to_remove = None
            for pos, user in self.positions.items():
                if user == username:
                    position_to_remove = pos
                    break
                    
            if position_to_remove:
                del self.positions[position_to_remove]
                
            # Remove widget if exists
            if username in self.remote_video_widgets:
                if self.remote_video_widgets[username] != "creating":
                    widget = self.remote_video_widgets[username]
                    self.client.gui.remove_video_widget(widget)
                    widget.deleteLater()
                    print(f"Removed video widget for {username}")
                else:
                    print(f"Removed placeholder for {username} (widget was being created)")
                    
                del self.remote_video_widgets[username]
                # Clear cached frames
                with self._pending_lock:
                    self.pending_frames.pop(username, None)
                
            # Clean up address mappings
            addrs_to_remove = []
            for addr, name in self.addr_to_username.items():
                if name == username:
                    addrs_to_remove.append(addr)
                    
            for addr in addrs_to_remove:
                del self.addr_to_username[addr]
            
            self.participants_changed_signal.emit()
                
            # Reorganize grid
            self.reorganize_grid()
        except Exception as e:
            print(f"Error removing remote video: {str(e)}")
            import traceback
            traceback.print_exc()