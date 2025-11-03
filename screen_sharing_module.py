"""
FusionMeet Screen Sharing Module
Captures and transmits screen content for presentations and demonstrations.
Implements single-presenter mode with TCP-based transmission for reliability.
"""

import mss
import pickle
import threading
import time
from PyQt5.QtCore import QTimer, QObject, pyqtSignal, pyqtSlot, Qt, QMetaObject, Q_ARG
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt5.QtGui import QImage, QPixmap, QIcon

from utils import send_with_size, resource_path


class ScreenShareHandler(QObject):
    """
    Manages screen capture, transmission, and viewing.
    Enforces single-presenter rule per session to prevent conflicts.
    """
    
    # PyQt signals for thread-safe GUI operations
    show_screen_share_signal = pyqtSignal(QWidget)
    hide_screen_share_signal = pyqtSignal()
    update_screen_signal = pyqtSignal(bytes, int, int)
    sharing_stopped_signal = pyqtSignal()
    sharing_started_signal = pyqtSignal()
    sharing_error_signal = pyqtSignal(str)
    presenter_status_changed = pyqtSignal(bool, str)  # (can_present, presenter_name)
    start_capture_signal = pyqtSignal()  # Triggered after server approval
    
    def __init__(self, client):
        """
        Initialize screen sharing handler.
        
        Args:
            client: Reference to main client instance
        """
        super().__init__()
        self.client = client
        self.is_sharing = False
        self.screen_capture = None
        self.share_timer = None
        self.display_widget = None # Defer creation
        
        # FIXED: Track presenter state
        self.current_presenter = None  # Username of current presenter
        self.can_present = True  # Whether this client can start presenting
        
        # Connect signals
        self.show_screen_share_signal.connect(self._show_screen_share_slot)
        self.hide_screen_share_signal.connect(self._hide_screen_share_slot)
        self.update_screen_signal.connect(self._update_screen_slot)
        self.sharing_stopped_signal.connect(self._sharing_stopped_slot)
        self.sharing_started_signal.connect(self._sharing_started_slot)
        self.sharing_error_signal.connect(self._sharing_error_slot)
        # FIXED: Connect start capture signal to slot
        self.start_capture_signal.connect(self._start_capture_slot)

    def start_sharing(self):
        """
        Request permission to start screen sharing.
        
        Returns:
            bool: True if request sent successfully, False otherwise
        """
        # Verify presenter permissions before requesting
        if not self.can_present:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(
                None,
                "Cannot Present",
                f"🚫 {self.current_presenter} is currently presenting.\n\n"
                f"Please wait for them to finish before starting your presentation."
            )
            print(f"❌ Cannot start sharing - {self.current_presenter} is presenting")
            return False
        
        if self.is_sharing:
            print("Screen sharing already active")
            return False
        
        # Send permission request to server (capture starts after approval)
        try:
            request = {
                'type': 'screen_share_request',
                'action': 'start'
            }
            send_with_size(self.client.tcp_socket, pickle.dumps(request))
            print("📤 Sent screen share start request to server")
            return True
        except Exception as e:
            error_msg = f"Failed to request screen sharing: {e}"
            print(error_msg)
            self.sharing_error_signal.emit(error_msg)
            return False
    
    def handle_screen_share_approved(self, data):
        """
        Handle server approval to begin screen sharing.
        
        Args:
            data: Approval message from server
        """
        print("✅ Screen share approved by server - starting capture")
        
        # Trigger capture start in GUI thread (QTimer requires GUI thread)
        self.start_capture_signal.emit()
    
    @pyqtSlot()
    def _start_capture_slot(self):
        """
        Begin screen capture in GUI thread.
        Creates MSS capture object and starts 2 FPS capture timer.
        """
        try:
            print("🎬 Starting screen capture in GUI thread...")
            
            # Initialize MSS screen capture
            self.screen_capture = mss.mss()
            
            # Create timer for periodic capture (must run in GUI thread)
            self.share_timer = QTimer()
            self.share_timer.timeout.connect(self.send_screen_frame)
            self.share_timer.start(500)  # 2 FPS
            
            self.is_sharing = True
            self.sharing_started_signal.emit()
            
            print("✅ Screen sharing started successfully")
        except Exception as e:
            error_msg = f"Error starting screen capture: {e}"
            print(error_msg)
            self.sharing_error_signal.emit(error_msg)
            import traceback
            traceback.print_exc()
    
    def handle_screen_share_denied(self, data):
        """
        Handle server denial when another user is presenting.
        
        Args:
            data: Denial message with reason and current presenter
        """
        reason = data.get('reason', 'Unknown reason')
        presenter = data.get('current_presenter', 'Someone')
        
        print(f"❌ Screen share denied: {reason}")
        
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.warning(
            None,
            "Presentation Denied",
            f"🚫 Cannot start presentation.\n\n{reason}"
        )
    
    def handle_presenter_changed(self, data):
        """
        Update presenter permissions based on server notification.
        
        Args:
            data: Presenter change event with status and username
        """
        is_presenting = data.get('is_presenting', False)
        presenter_name = data.get('presenter', '')
        
        print(f"📢 Presenter changed: {presenter_name if is_presenting else 'None'}")
        
        # Update presenter state and permissions
        if is_presenting:
            self.current_presenter = presenter_name
            self.can_present = (presenter_name == self.client.username)
        else:
            self.current_presenter = None
            self.can_present = True
        
        # Notify GUI to update button state
        self.presenter_status_changed.emit(self.can_present, presenter_name or "")
        
        print(f"✅ Can present: {self.can_present}, Current presenter: {self.current_presenter}")

    def stop_sharing(self):
        """
        Stop screen sharing and notify all participants.
        Releases capture resources and updates server presenter status.
        """
        if not self.is_sharing:
            return
            
        try:
            print("Stopping screen sharing...")
            self.is_sharing = False
            
            # Stop capture timer
            if self.share_timer:
                self.share_timer.stop()
                self.share_timer = None
                
            # Release MSS resources
            self.screen_capture = None
            
            # Notify other clients to hide display
            try:
                stop_notification = {
                    'type': 'screen_stop',
                    'username': self.client.username
                }
                send_with_size(self.client.tcp_socket, pickle.dumps(stop_notification))
                print("📤 Sent screen_stop notification to other clients")
            except Exception as e:
                print(f"Error sending screen_stop notification: {e}")
            
            # Notify server to free presenter slot
            try:
                request = {
                    'type': 'screen_share_request',
                    'action': 'stop'
                }
                send_with_size(self.client.tcp_socket, pickle.dumps(request))
                print("📤 Sent screen share stop request to server")
            except Exception as e:
                print(f"Error notifying server of stop: {e}")
            
            self.sharing_stopped_signal.emit()
            self.hide_screen_share_signal.emit()
            
            print("Screen sharing stopped successfully")
        except Exception as e:
            error_msg = f"Error stopping screen sharing: {str(e)}"
            print(error_msg)
            self.sharing_error_signal.emit(error_msg)
            import traceback
            traceback.print_exc()

    def send_screen_frame(self):
        """
        Capture and transmit screen frame to all participants.
        Compresses using JPEG (70% quality) to reduce bandwidth.
        Sends via TCP for reliability.
        """
        if not (self.is_sharing and self.screen_capture):
            return
            
        try:
            # Verify client connection exists
            if not self.client or not hasattr(self.client, 'tcp_socket') or self.client.tcp_socket is None:
                print("Client or TCP socket is not available")
                self.stop_sharing()
                return
                
            # Get primary monitor (index 1 for most systems)
            try:
                monitor = self.screen_capture.monitors[1]
            except IndexError:
                monitor = self.screen_capture.monitors[0]
                
            # Capture screen
            try:
                sct_img = self.screen_capture.grab(monitor)
            except Exception as e:
                print(f"Screen capture failed: {str(e)}")
                self.stop_sharing()
                return
            
            # Validate capture data
            if not hasattr(sct_img, 'rgb') or not sct_img.rgb:
                print("Invalid screen capture - no RGB data")
                return
                
            # Try OpenCV compression (best quality/bandwidth ratio)
            opencv_available = False
            numpy_available = False
            
            try:
                import numpy as np
                numpy_available = True
                import cv2
                opencv_available = True
                
                if opencv_available and numpy_available:
                    # Convert to numpy array
                    img_array = np.array(sct_img)
                    
                    # Resize to max 800px dimension (maintain aspect ratio)
                    height, width = img_array.shape[:2]
                    max_dimension = 800
                    
                    if max(width, height) > max_dimension:
                        scale_factor = max_dimension / max(width, height)
                        new_width = int(width * scale_factor)
                        new_height = int(height * scale_factor)
                        img_array = cv2.resize(img_array, (new_width, new_height))
                        print(f"Resized screen share from {width}x{height} to {new_width}x{new_height}")
                        
                    # Convert to RGB (MSS may return BGRA)
                    if img_array.shape[2] == 4:
                        img_array = cv2.cvtColor(img_array, cv2.COLOR_BGRA2RGB)
                    elif img_array.shape[2] == 3:
                        img_array = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB)
                    
                    # JPEG compression at 70% quality
                    _, jpeg_bytes = cv2.imencode('.jpg', img_array, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    compressed_frame = jpeg_bytes.tobytes()
                    
                    payload = {
                        'type': 'screen',
                        'frame': compressed_frame,
                        'format': 'jpeg',
                        'size': (img_array.shape[1], img_array.shape[0]),
                        'username': self.client.username
                    }
                else:
                    raise ImportError("OpenCV or NumPy not available")
                    
            except (ImportError, NameError, Exception) as e:
                # Fallback: raw RGB with manual downsampling
                print(f"Using fallback raw RGB format: {str(e)}")
                
                try:
                    width, height = sct_img.size
                    
                    # Downsample large screens
                    if max(width, height) > 800:
                        # Manual pixel-skipping downsampling
                        try:
                            scale_factor = max(width, height) / 800
                            step = max(2, int(scale_factor))
                            
                            rgb_data = sct_img.rgb
                            raw_bytes = bytearray()
                            
                            new_width = width // step
                            new_height = height // step
                            
                            # Sample every Nth pixel
                            for y in range(0, height, step):
                                for x in range(0, width, step):
                                    pos = 3 * (y * width + x)
                                    if pos + 2 < len(rgb_data):
                                        raw_bytes.extend(rgb_data[pos:pos+3])
                            
                            payload = {
                                'type': 'screen',
                                'frame': bytes(raw_bytes),
                                'format': 'rgb',
                                'size': (new_width, new_height),
                                'username': self.client.username
                            }
                            print(f"Using simple downsampling: {new_width}x{new_height}")
                        except Exception as e3:
                            print(f"Downsampling failed: {e3}, using original size")
                            payload = {
                                'type': 'screen',
                                'frame': sct_img.rgb,
                                'format': 'rgb',
                                'size': sct_img.size,
                                'username': self.client.username
                            }
                    else:
                        payload = {
                            'type': 'screen',
                            'frame': sct_img.rgb,
                            'format': 'rgb',
                            'size': sct_img.size,
                            'username': self.client.username
                        }
                except Exception as e2:
                    print(f"Fallback also failed, using original size: {str(e2)}")
                    payload = {
                        'type': 'screen',
                        'frame': sct_img.rgb,
                        'format': 'rgb',
                        'size': sct_img.size,
                        'username': self.client.username
                    }
            
            data = pickle.dumps(payload)
            
            # Skip frame if packet exceeds 1MB
            MAX_PACKET_SIZE = 1024 * 1024
            if len(data) > MAX_PACKET_SIZE:
                print(f"Screen frame too large: {len(data)} bytes, skipping")
                return
                
            print(f"Sending screen frame: {payload['size'][0]}x{payload['size'][1]}, {len(data)} bytes, format: {payload.get('format', 'rgb')}")
            send_with_size(self.client.tcp_socket, data)
            
        except ConnectionError as e:
            print(f"Connection error in screen sharing: {str(e)}")
            self.stop_sharing()
        except Exception as e:
            print(f"Error capturing or sending screen: {str(e)}")
            import traceback
            traceback.print_exc()

    def handle_screen_frame(self, data):
        """
        Process incoming screen share frame from presenter.
        
        Args:
            data: Pickled screen frame or stop notification
        """
        try:
            payload = pickle.loads(data)
            
            # Handle presenter stop notification
            if payload['type'] == 'screen_stop':
                username = payload.get('username', 'Someone')
                print(f"Received screen sharing stop notification from {username}")
                self.hide_screen_share_signal.emit()
                return
                
            # Process screen frame
            elif payload['type'] == 'screen':
                username = payload.get('username', 'Someone')
                print(f"Received screen sharing frame from {username}")
                
                # Create display widget if first frame
                if not self.display_widget:
                    # Create in main thread
                    QMetaObject.invokeMethod(
                        self,
                        "create_display_widget",
                        Qt.BlockingQueuedConnection
                    )
                
                if self.display_widget:
                    frame_bytes = payload['frame']
                    width, height = payload['size']
                    frame_format = payload.get('format', 'rgb')
                    print(f"Screen frame size: {width}x{height}, {len(frame_bytes)} bytes, format: {frame_format}")
                    
                    # Update display in GUI thread
                    self.update_screen_signal.emit(frame_bytes, width, height)
                else:
                    print("Display widget not created yet")
                    
        except (pickle.UnpicklingError, KeyError) as e:
            print(f"Error processing screen share data: {str(e)}")
        except Exception as e:
            print(f"Unexpected error in screen sharing: {str(e)}")
            import traceback
            traceback.print_exc()
            
    @pyqtSlot()
    def create_display_widget(self):
        """
        Create screen share display widget in GUI thread.
        Replaces video grid with fullscreen presenter view.
        """
        try:
            if self.display_widget and not self.display_widget.isHidden():
                print("Screen share display widget already exists and is visible")
                return
                
            # Clean up old widget if exists
            if self.display_widget:
                print("Removing old screen share display widget")
                self.display_widget.deleteLater()
                
            print("Creating new screen share display widget in main thread")
            self.display_widget = ScreenShareDisplay()

            # Track widget destruction to clear reference
            try:
                self.display_widget.destroyed.connect(self._on_display_destroyed)
            except Exception:
                pass

            self.show_screen_share_signal.emit(self.display_widget)
        except Exception as e:
            print(f"Error creating display widget: {str(e)}")
            import traceback
            traceback.print_exc()
    
    @pyqtSlot()
    def _on_display_destroyed(self):
        """Clear widget reference on Qt destruction."""
        print("ScreenShareDisplay widget destroyed - clearing reference")
        self.display_widget = None
            
    @pyqtSlot(QWidget)
    def _show_screen_share_slot(self, widget):
        """
        Show screen share widget in GUI thread.
        
        Args:
            widget: ScreenShareDisplay widget to show
        """
        if self.client and self.client.gui:
            self.client.gui.show_screen_share(widget)
            
    @pyqtSlot()
    def _hide_screen_share_slot(self):
        """Hide screen share widget and clear reference."""
        if self.display_widget:
            print("Clearing screen share display widget reference")
            self.display_widget = None
        
        if self.client and self.client.gui:
            self.client.gui.hide_screen_share()
            
    @pyqtSlot(bytes, int, int)
    def _update_screen_slot(self, frame_bytes, width, height):
        """
        Update screen frame in GUI thread.
        
        Args:
            frame_bytes: Raw image data (JPEG or RGB)
            width: Frame width in pixels
            height: Frame height in pixels
        """
        try:
            if not self.display_widget:
                return

            # Check if Qt widget still valid
            try:
                import importlib
                sip = None
                try:
                    sip = importlib.import_module('sip')
                except Exception:
                    sip = None

                if sip is not None and getattr(sip, 'isdeleted', None):
                    try:
                        if sip.isdeleted(self.display_widget):
                            self.display_widget = None
                            return
                    except Exception:
                        pass
            except Exception:
                pass

            # Update frame safely
            try:
                self.display_widget.set_frame(frame_bytes, width, height)
            except RuntimeError as re:
                print(f"Warning: screen display widget deleted during update: {re}")
                self.display_widget = None
            except Exception as e:
                print(f"Unexpected error updating screen widget: {e}")
        except Exception as e:
            print(f"Error in _update_screen_slot: {e}")
            
    @pyqtSlot()
    def _sharing_stopped_slot(self):
        """Update GUI button when sharing stops."""
        if self.client and self.client.gui:
            print("Screen sharing stopped - updating GUI")
            if hasattr(self.client.gui, 'share_screen_button'):
                self.client.gui.share_screen_button.setIcon(QIcon(resource_path("icons/screen_share.png")))
                self.client.gui.share_screen_button.setEnabled(True)
                
    @pyqtSlot()
    def _sharing_started_slot(self):
        """Update GUI button when sharing starts."""
        if self.client and self.client.gui:
            print("Screen sharing started - updating GUI")
            if hasattr(self.client.gui, 'share_screen_button'):
                self.client.gui.share_screen_button.setIcon(QIcon(resource_path("icons/screen_share_off.png")))
                self.client.gui.share_screen_button.setEnabled(True)
                
    @pyqtSlot(str)
    def _sharing_error_slot(self, error_msg):
        """
        Handle screen sharing errors and notify user.
        
        Args:
            error_msg: Error description
        """
        print(f"Screen sharing error: {error_msg}")
        if self.is_sharing:
            self.stop_sharing()
            
        if self.client and hasattr(self.client, 'gui') and hasattr(self.client.gui, 'add_chat_message'):
            self.client.gui.add_chat_message("System", f"Screen sharing error: {error_msg}")

class ScreenShareDisplay(QWidget):
    """
    Fullscreen widget for displaying presenter's screen.
    Replaces video grid during screen sharing sessions.
    Shows FPS counter and scales frame to fit window.
    """
    
    set_frame_signal = pyqtSignal(bytes, int, int)
    
    def __init__(self, parent=None):
        """
        Initialize screen share display.
        
        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        
        # Main display label
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setMinimumSize(800, 600)
        
        # Info bar with FPS counter
        self.info_label = QLabel("Screen Sharing Active", self)
        self.info_label.setStyleSheet("background-color: rgba(0, 0, 0, 150); color: white; padding: 5px;")
        self.info_label.setAlignment(Qt.AlignCenter)
        
        layout = QVBoxLayout()
        layout.addWidget(self.info_label)
        layout.addWidget(self.label, 1)
        self.setLayout(layout)
        
        self.set_frame_signal.connect(self._set_frame_slot)
        
        # FPS tracking
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.fps = 0
        
        # Update FPS display every second
        self.fps_timer = QTimer()
        self.fps_timer.timeout.connect(self._update_fps_display)
        self.fps_timer.start(1000)
        
        self._clear_frame()
        
    def _update_fps_display(self):
        """Update info label with current framerate."""
        if self.fps > 0:
            self.info_label.setText(f"Screen Sharing Active - {self.fps:.1f} FPS")
        else:
            self.info_label.setText("Screen Sharing Active")
        
    def _clear_frame(self):
        """Display blank black screen when no frame available."""
        empty = QPixmap(800, 600)
        empty.fill(Qt.black)
        self.label.setPixmap(empty)

    def set_frame(self, frame_bytes, width, height):
        """
        Thread-safe frame update via signal.
        
        Args:
            frame_bytes: Raw image data (JPEG or RGB)
            width: Frame width in pixels
            height: Frame height in pixels
        """
        self.set_frame_signal.emit(frame_bytes, width, height)
        
    @pyqtSlot(bytes, int, int)
    def _set_frame_slot(self, frame_bytes, width, height):
        """
        Update displayed frame in GUI thread.
        
        Args:
            frame_bytes: Raw image data (JPEG or RGB)
            width: Frame width in pixels
            height: Frame height in pixels
        """
        try:
            # Update FPS calculation
            self.frame_count += 1
            current_time = time.time()
            time_diff = current_time - self.last_fps_time
            
            if time_diff >= 1.0:
                self.fps = self.frame_count / time_diff
                self.frame_count = 0
                self.last_fps_time = current_time
            
            # Detect JPEG format by magic bytes (FF D8 FF)
            is_jpeg = (len(frame_bytes) >= 3 and 
                       frame_bytes[0] == 0xFF and 
                       frame_bytes[1] == 0xD8 and 
                       frame_bytes[2] == 0xFF)
            
            if is_jpeg:
                # Load JPEG directly
                image = QImage()
                image.loadFromData(frame_bytes, 'JPEG')
            else:
                # Decode raw RGB
                image = QImage(frame_bytes, width, height, width * 3, QImage.Format_RGB888)
            
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                scaled_pixmap = pixmap.scaled(
                    self.label.size(),
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
                self.label.setPixmap(scaled_pixmap)
            else:
                print("Error: Created QImage is null")
                self._clear_frame()
        except Exception as e:
            print(f"Error setting screen frame: {str(e)}")
            import traceback
            traceback.print_exc()
            self._clear_frame()
            
    def hideEvent(self, event):
        """Stop FPS timer when hidden."""
        self.fps_timer.stop()
        super().hideEvent(event)
        
    def showEvent(self, event):
        """Restart FPS timer when shown."""
        self.fps_timer.start(1000)
        super().showEvent(event)
