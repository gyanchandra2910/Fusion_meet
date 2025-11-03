"""
FusionMeet File Sharing Module
Handles peer-to-peer file upload, distribution, and download within sessions.
Uses TCP for reliable chunked transfer with progress tracking.
"""

import os
import pickle
import struct
import time
from PyQt5.QtWidgets import QFileDialog, QProgressDialog, QMessageBox, QWidget, QDialog, QLabel, QHBoxLayout, QVBoxLayout, QPushButton, QStyle
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QMetaObject, Q_ARG
from PyQt5.QtGui import QPalette, QColor, QPixmap

from utils import send_with_size, receive_with_size
from config import FILE_CHUNK_SIZE, DEFAULT_DOWNLOAD_DIR, MAX_FILE_SIZE


class FileSharingHandler(QObject):
    """
    Manages file sharing functionality.
    Coordinates file uploads to server and downloads from other clients.
    """
    
    # PyQt signals for async notifications
    new_file_available = pyqtSignal(str, int)  # (filename, size)
    download_progress = pyqtSignal(str, int, int)  # (filename, bytes_received, total_size)
    download_complete = pyqtSignal(str, str)  # (filename, filepath)
    
    def __init__(self, client):
        """
        Initialize file sharing handler.
        
        Args:
            client: Reference to main client instance
        """
        super().__init__()
        self.client = client
        self.files = {}  # Available files in session: {filename: size}
        self.downloads = {}  # Active downloads: {filename: {'path', 'file', 'size', 'received'}}
        
        # Helper for creating styled message boxes
        self.create_styled_msgbox = lambda title, text, icon_type: self._create_msgbox(title, text, icon_type)
        
    def _create_msgbox(self, title, text, icon_type):
        """
        Create custom styled message dialog with light theme.
        Overrides app-wide dark theme for better readability.
        
        Args:
            title: Dialog window title
            text: Message content to display
            icon_type: Icon type (info, warning, critical, question)
            
        Returns:
            QDialog: Configured dialog ready to show
        """
        dlg = QDialog(self.client.gui)
        dlg.setWindowTitle(title)
        dlg.setModal(True)
        dlg.setMinimumWidth(480)
        dlg.setAttribute(Qt.WA_StyledBackground, True)
        dlg.setAutoFillBackground(True)

        # Force light theme styling (overrides global dark theme)
        dlg.setStyleSheet("""
            QDialog {
                background-color: #f0f0f0;
            }
            /* Force light colors for content widget and all children */
            QWidget#dialog_content, QWidget#dialog_content * {
                background-color: #f0f0f0 !important;
                color: #000000 !important;
            }
            QLabel#info {
                background-color: #f0f0f0 !important;
                color: #000000 !important;
                font-size: 13px;
                padding: 10px;
            }
            QLabel.icon_label {
                background-color: transparent !important;
            }
            QTextEdit, QTextBrowser, QPlainTextEdit {
                background-color: #FFFFFF !important;
                color: #000000 !important;
                border: 1px solid #CCCCCC !important;
                padding: 6px !important;
                border-radius: 3px !important;
            }
            QPushButton#okbtn {
                background-color: #4CAF50 !important;
                color: #FFFFFF !important;
                padding: 8px 16px !important;
                border-radius: 6px !important;
                font-weight: bold !important;
                min-width: 80px !important;
                border: none !important;
            }
            QPushButton#okbtn:hover {
                background-color: #45a049 !important;
            }
            QPushButton#okbtn:pressed {
                background-color: #3d8b40 !important;
            }
        """)

        # Create a white content widget that will hold everything (this prevents odd child widgets painting darker)
        content = QWidget(dlg)
        content.setObjectName("dialog_content")
        content.setAttribute(Qt.WA_StyledBackground, True)
        content.setAutoFillBackground(True)

        # Ensure palette for content explicitly light gray
        pal = content.palette()
        pal.setColor(QPalette.Window, QColor("#f0f0f0"))
        pal.setColor(QPalette.Base, QColor("#f0f0f0"))
        pal.setColor(QPalette.WindowText, QColor("#000000"))
        pal.setColor(QPalette.Text, QColor("#000000"))
        content.setPalette(pal)

        # Layouts
        main_layout = QVBoxLayout(dlg)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(content)

        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(10)

        # Row: icon + message
        row = QHBoxLayout()
        row.setSpacing(12)

        # Icon
        style = dlg.style()
        if icon_type == "critical":
            icon = style.standardIcon(QStyle.SP_MessageBoxCritical)
        elif icon_type == "warning":
            icon = style.standardIcon(QStyle.SP_MessageBoxWarning)
        else:
            icon = style.standardIcon(QStyle.SP_MessageBoxInformation)
        icon_pix = icon.pixmap(48, 48)

        icon_label = QLabel()
        icon_label.setObjectName("icon_label")
        icon_label.setProperty("class", "icon_label")
        icon_label.setPixmap(icon_pix)
        icon_label.setFixedSize(56, 56)
        icon_label.setStyleSheet("background: transparent;")  # ensure icon doesn't get boxed

        # Info label — prefer plain QLabel (word-wrapped)
        info_label = QLabel(text)
        info_label.setWordWrap(True)
        info_label.setObjectName("info")
        info_label.setTextInteractionFlags(Qt.TextSelectableByMouse)  # allow copy
        info_label.setStyleSheet("background-color: #f0f0f0; color: #000000;")  # extra safety
        info_label.setAutoFillBackground(True)

        row.addWidget(icon_label, 0, Qt.AlignTop)
        row.addWidget(info_label, 1)

        content_layout.addLayout(row)

        # Spacer then OK button aligned right
        content_layout.addStretch()

        ok_btn = QPushButton("OK")
        ok_btn.setObjectName("okbtn")
        ok_btn.clicked.connect(dlg.accept)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(ok_btn)
        content_layout.addLayout(btn_row)

        # Final safety: set light gray palette on known widget children to override any global theme
        for w in dlg.findChildren(QWidget):
            try:
                w.setAutoFillBackground(True)
                wp = w.palette()
                wp.setColor(QPalette.Window, QColor("#f0f0f0"))
                wp.setColor(QPalette.Base, QColor("#f0f0f0"))
                wp.setColor(QPalette.WindowText, QColor("#000000"))
                wp.setColor(QPalette.Text, QColor("#000000"))
                w.setPalette(wp)
            except Exception:
                pass

        return dlg


    def send_file(self):
        """
        Open file selection dialog and upload chosen file to session.
        File is copied to uploads directory and announced to server.
        """
        # Create styled file selection dialog
        file_dialog = QFileDialog(self.client.gui)
        file_dialog.setWindowTitle("Select File to Share")
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        
        # Apply styling to make it visible and professional
        file_dialog.setStyleSheet("""
            QFileDialog {
                background-color: #f0f0f0;
                color: #000000;
            }
            QFileDialog QWidget {
                background-color: #f0f0f0;
                color: #000000;
            }
            QLabel {
                background-color: #f0f0f0;
                color: #000000;
                font-size: 12px;
            }
            QLineEdit {
                background-color: #FFFFFF;
                color: #000000;
                border: 1px solid #CCCCCC;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 6px 16px;
                border: none;
                border-radius: 4px;
                min-width: 70px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QTreeView, QListView {
                background-color: #FFFFFF;
                color: #000000;
                border: 1px solid #CCCCCC;
                alternate-background-color: #f8f8f8;
            }
            QTreeView::item, QListView::item {
                background-color: #FFFFFF;
                color: #000000;
                padding: 4px;
            }
            QTreeView::item:hover, QListView::item:hover {
                background-color: #E8F5E9;
                color: #000000;
            }
            QTreeView::item:selected, QListView::item:selected {
                background-color: #4CAF50;
                color: white;
            }
            QHeaderView::section {
                background-color: #F5F5F5;
                color: #000000;
                padding: 5px;
                border: 1px solid #CCCCCC;
                font-weight: bold;
            }
            QComboBox {
                background-color: #FFFFFF;
                color: #000000;
                border: 1px solid #CCCCCC;
                padding: 5px;
                border-radius: 3px;
            }
            QComboBox:hover {
                border: 1px solid #4CAF50;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                color: #000000;
                selection-background-color: #4CAF50;
                selection-color: white;
                border: 1px solid #CCCCCC;
            }
            QComboBox::item {
                background-color: #FFFFFF;
                color: #000000;
            }
            QComboBox::item:selected {
                background-color: #4CAF50;
                color: white;
            }
        """)

        # Use non-native dialog for consistent styling
        file_dialog.setOption(QFileDialog.DontUseNativeDialog, True)      
        if file_dialog.exec_() == QFileDialog.Accepted:
            files = file_dialog.selectedFiles()
            if files:
                filepath = files[0]
            else:
                return  # No file selected
        else:
            return  # Dialog cancelled
        
        # Extract file information
        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)
        
        # Validate file size against maximum limit
        if filesize > MAX_FILE_SIZE:
            msg_box = self.create_styled_msgbox(
                "File Too Large", 
                f"The selected file exceeds the maximum allowed size of {self.format_size(MAX_FILE_SIZE)}.",
                "warning"
            )
            msg_box.exec_()
            return

        # Create uploads directory for file storage
        uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        
        # Copy file to uploads directory for persistent sharing
        try:
            import shutil
            uploads_path = os.path.join(uploads_dir, filename)
            shutil.copy2(filepath, uploads_path)
            print(f"Saved a copy of {filename} to uploads directory for future sharing")
            
            # Use the uploaded copy from now on
            filepath = uploads_path
        except Exception as e:
            print(f"Warning: Could not save copy of file to uploads directory: {e}")
        
        # Announce file availability to server
        file_info = {
            'type': 'file_info',
            'filename': filename,
            'filesize': filesize,
            'sender': self.client.username
        }
        send_with_size(self.client.tcp_socket, pickle.dumps(file_info))
        
        # Add to local files list for immediate UI update
        self.files[filename] = filesize
        
        # Emit signal to update UI
        self.new_file_available.emit(filename, filesize)
        print(f"Added file to local list: {filename} ({filesize} bytes)")

        # Upload file data to server
        self.upload_file(filepath, filename)

    def upload_file(self, filepath, filename):
        """
        Upload file to server in chunks with progress tracking.
        Displays progress dialog during upload.
        
        Args:
            filepath: Full path to file on disk
            filename: Name of file being uploaded
        """
        filesize = os.path.getsize(filepath)
        
        # Create upload progress dialog
        progress = QProgressDialog(
            f"Uploading {filename}...\n0% complete (0 KB of {self.format_size(filesize)})", 
            "Cancel", 
            0, 
            filesize, 
            self.client.gui
        )
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumWidth(400)
        
        # Style the progress dialog
        progress.setStyleSheet("""
            QProgressDialog {
                background-color: #f0f0f0;
                border: 1px solid #CCCCCC;
                border-radius: 6px;
            }
            QProgressDialog QLabel {
                background-color: #f0f0f0;
                color: #000000;
                font-size: 13px;
                padding: 10px;
            }
            QProgressBar {
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                text-align: center;
                background-color: #FFFFFF;
                color: #000000;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
            QPushButton {
                background-color: #FF5252;
                color: white;
                font-weight: bold;
                padding: 6px 16px;
                border: none;
                border-radius: 4px;
                min-width: 70px;
            }
            QPushButton:hover {
                background-color: #E53935;
            }
        """)
        
        progress.show()
        
        # Add message to chat at start of upload
        if hasattr(self.client, 'gui'):
            self.client.gui.add_chat_message("System", f"Uploading <b>{filename}</b>...")

        try:
            start_time = time.time()
            # Open with buffering for better performance
            with open(filepath, 'rb', buffering=8192) as f:
                sent_bytes = 0
                # Use configured chunk size for better performance
                chunk_size = FILE_CHUNK_SIZE
                
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break  # End of file
                    if progress.wasCanceled():
                        print("Upload cancelled.")
                        # Optionally send a cancellation message to the server
                        return

                    data = {
                        'type': 'file_chunk', 
                        'filename': filename, 
                        'chunk': chunk,
                        # No requester field here - it will be added by server when forwarding
                    }
                    send_with_size(self.client.tcp_socket, pickle.dumps(data))
                    sent_bytes += len(chunk)
                    
                    # Update progress only every ~100KB to reduce overhead
                    if sent_bytes % 102400 < chunk_size or sent_bytes >= filesize:
                        progress.setValue(sent_bytes)
                        
                            # Update progress text with speed and ETA
                        elapsed = time.time() - start_time
                        if elapsed > 0:
                                speed = sent_bytes / elapsed
                                percent = int(100 * sent_bytes / filesize)
                                
                                speed_str = self.format_size(speed) + "/s"
                                
                                # Calculate ETA
                                if speed > 0:
                                    remaining_bytes = filesize - sent_bytes
                                    eta_seconds = remaining_bytes / speed
                                    if eta_seconds < 60:
                                        eta = f"{int(eta_seconds)} seconds"
                                    elif eta_seconds < 3600:
                                        eta = f"{int(eta_seconds / 60)} minutes"
                                    else:
                                        eta = f"{int(eta_seconds / 3600)} hours, {int((eta_seconds % 3600) / 60)} minutes"
                                else:
                                    eta = "unknown"
                                    
                                # Add a message at 50% complete
                                if percent >= 50 and (sent_bytes - chunk_size) * 100 / filesize < 50:
                                    if hasattr(self.client, 'gui'):
                                        self.client.gui.add_chat_message("System", f"Upload of {filename} is 50% complete")
                                        
                        progress.setLabelText(
                                f"Uploading {filename}...\n"
                                f"{percent}% complete ({self.format_size(sent_bytes)} of {self.format_size(filesize)})\n"
                                f"Speed: {speed_str} | ETA: {eta}"
                            )
            
            # Send end-of-file marker after the loop finishes
            eof_marker = {'type': 'file_end', 'filename': filename}
            send_with_size(self.client.tcp_socket, pickle.dumps(eof_marker))
            print(f"Finished uploading {filename}")
            
            # Refresh the UI to show the file is now available
            if hasattr(self.client, 'gui'):
                self.client.gui.refresh_files()
                self.client.gui.add_chat_message("System", f"<b>{filename}</b> uploaded successfully!")
            
            # Show a success message
            if hasattr(self.client, 'gui'):
                # Create and show a styled success message
                msg_box = self.create_styled_msgbox(
                    "Upload Complete", 
                    f"The file {filename} has been uploaded successfully.",
                    "information"
                )
                msg_box.exec_()
                
                # Make sure GUI refreshes file list
                if hasattr(self.client.gui, 'refresh_files'):
                    self.client.gui.refresh_files()

        except FileNotFoundError:
            print(f"Error: File not found at {filepath}")
        finally:
            progress.setValue(os.path.getsize(filepath))
            progress.close()

    def handle_file_info(self, data):
        """
        Process incoming file availability notifications from server.
        Handles file_info (new file), available_files (list), and file_request messages.
        
        Args:
            data: Pickled payload containing file information
        """
        try:
            payload = pickle.loads(data)
            msg_type = payload.get('type')
            
            # Log message type for debugging
            print(f"handle_file_info: Processing message of type {msg_type}")
            
            if msg_type == 'file_info':
                # Process new file shared by another client
                filename = payload['filename']
                filesize = payload['filesize']
                sender = payload.get('sender', 'Unknown')
                
                # Store file info and emit signal
                self.files[filename] = filesize
                self.new_file_available.emit(filename, filesize)
                
                print(f"New file available: {filename} ({filesize} bytes) from {sender}")
                
                # Show notification in chat
                if hasattr(self.client, 'gui'):
                    msg = f"{sender} shared a file: <b>{filename}</b> ({self.format_size(filesize)}) - See Shared Files panel to download"
                    self.client.gui.add_chat_message("System", msg)
            elif msg_type == 'available_files':
                # Receive list of all available files from server (sent on join)
                available_files = payload.get('files', {})
                print(f"Received available files list from server: {len(available_files)} files")
                
                # Update local file list and notify UI
                self.files.update(available_files)
                for filename, filesize in available_files.items():
                    self.new_file_available.emit(filename, filesize)
                
                # Refresh files panel
                if hasattr(self.client, 'gui') and hasattr(self.client.gui, 'refresh_files'):
                    self.client.gui.refresh_files()
            elif msg_type == 'file_request':
                # Another client is requesting a file we shared
                print("File request received from server - handling request")
                filename = payload.get('filename')
                requester = payload.get('requester')
                print(f"Request details - filename: {filename}, requester: {requester}")
                
                self.handle_file_request(payload)
        except (pickle.UnpicklingError, KeyError) as e:
            print(f"Error handling file info: {e}")
            import traceback
            traceback.print_exc()
        except (pickle.UnpicklingError, KeyError) as e:
            print(f"Error handling file info: {e}")

    def request_download(self, filename):
        """
        Initiate download of a shared file from another client.
        Shows save dialog, opens file for writing, and sends request to server.
        
        Args:
            filename: Name of the file to download
            
        Raises:
            ValueError: If file is not in available files list
        """
        if filename not in self.files:
            raise ValueError(f"File {filename} not available for download")
        
        # Create downloads directory
        download_dir = os.path.join(os.path.expanduser("~"), "Downloads", DEFAULT_DOWNLOAD_DIR)
        os.makedirs(download_dir, exist_ok=True)
        
        default_save_path = os.path.join(download_dir, filename)
        
        # Create and style save file dialog
        file_dialog = QFileDialog(self.client.gui)
        file_dialog.setWindowTitle("Save File As")
        file_dialog.setAcceptMode(QFileDialog.AcceptSave)
        file_dialog.setFileMode(QFileDialog.AnyFile)
        file_dialog.setDirectory(download_dir)
        file_dialog.selectFile(filename)
        file_dialog.setNameFilter("All Files (*)")
        
        # Apply the same styling as the open dialog
        file_dialog.setStyleSheet("""
            QFileDialog {
                background-color: #f0f0f0;
                color: #000000;
            }
            QFileDialog QWidget {
                background-color: #f0f0f0;
                color: #000000;
            }
            QLabel {
                background-color: #f0f0f0;
                color: #000000;
                font-size: 12px;
            }
            QLineEdit {
                background-color: #FFFFFF;
                color: #000000;
                border: 1px solid #CCCCCC;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 6px 16px;
                border: none;
                border-radius: 4px;
                min-width: 70px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QTreeView, QListView {
                background-color: #FFFFFF;
                color: #000000;
                border: 1px solid #CCCCCC;
                alternate-background-color: #f8f8f8;
            }
            QTreeView::item, QListView::item {
                background-color: #FFFFFF;
                color: #000000;
                padding: 4px;
            }
            QTreeView::item:hover, QListView::item:hover {
                background-color: #E8F5E9;
                color: #000000;
            }
            QTreeView::item:selected, QListView::item:selected {
                background-color: #4CAF50;
                color: white;
            }
            QHeaderView::section {
                background-color: #F5F5F5;
                color: #000000;
                padding: 5px;
                border: 1px solid #CCCCCC;
                font-weight: bold;
            }
            QComboBox {
                background-color: #FFFFFF;
                color: #000000;
                border: 1px solid #CCCCCC;
                padding: 5px;
                border-radius: 3px;
            }
            QComboBox:hover {
                border: 1px solid #4CAF50;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                color: #000000;
                selection-background-color: #4CAF50;
                selection-color: white;
                border: 1px solid #CCCCCC;
            }
            QComboBox::item {
                background-color: #FFFFFF;
                color: #000000;
            }
            QComboBox::item:selected {
                background-color: #4CAF50;
                color: white;
            }
        """)

        file_dialog.setOption(QFileDialog.DontUseNativeDialog, True)

        
        if file_dialog.exec_() == QFileDialog.Accepted:
            files = file_dialog.selectedFiles()
            if files:
                save_path = files[0]
            else:
                return  # User canceled
        else:
            return  # User canceled
        
        try:
            # Open file with 64KB buffer for better write performance
            file_obj = open(save_path, 'wb', buffering=65536)
            
            # Store download state
            self.downloads[filename] = {
                'path': save_path,
                'file': file_obj,
                'size': self.files[filename],
                'received': 0,
                'start_time': time.time()  # Track download speed
            }
            
            # Send download request to server
            req = {'type': 'file_request', 'filename': filename}
            print(f"Sending file request for {filename} to server")
            send_with_size(self.client.tcp_socket, pickle.dumps(req))
            
            # Show progress tracking
            self.show_download_progress(filename)
            
            print(f"Started download for {filename} to {save_path}")
            
        except Exception as e:
            # Show error dialog
            if hasattr(self.client, 'gui'):
                msg_box = self.create_styled_msgbox(
                    "Download Error", 
                    f"Failed to start download: {str(e)}",
                    "critical"
                )
                msg_box.exec_()
            
            # Clean up download state
            if filename in self.downloads:
                if 'file' in self.downloads[filename]:
                    self.downloads[filename]['file'].close()
                del self.downloads[filename]

    def show_download_progress(self, filename):
        """
        Initialize progress tracking for a file download.
        Emits signals and creates update callback for periodic progress updates.
        
        Args:
            filename: Name of file being downloaded
        """
        if filename not in self.downloads:
            return
        
        from PyQt5.QtCore import QMetaObject, Qt, Q_ARG
        download_info = self.downloads[filename]
        filesize = download_info['size']
        
        # Emit initial progress signal
        if hasattr(self.client, 'gui'):
            self.download_progress.emit(filename, 0, filesize)
            print(f"Downloading {filename}... (0%)")
        
        print(f"Download started for {filename}")
        
        # Progress update callback (called periodically as chunks arrive)
        def update_progress_text():
            if filename not in self.downloads:
                return
                
            current_info = self.downloads[filename]
            received = current_info['received']
            percent = int(100 * received / filesize) if filesize > 0 else 0
            elapsed = time.time() - current_info['start_time']
            
            # Calculate download speed and ETA
            if elapsed > 0:
                speed = received / elapsed if received > 0 else 0
                speed_str = self.format_size(speed) + "/s"
                
                if speed > 0:
                    remaining_bytes = filesize - received
                    eta_seconds = remaining_bytes / speed
                    if eta_seconds < 60:
                        eta = f"{int(eta_seconds)} seconds"
                    elif eta_seconds < 3600:
                        eta = f"{int(eta_seconds / 60)} minutes"
                    else:
                        eta = f"{int(eta_seconds / 3600)} hours, {int((eta_seconds % 3600) / 60)} minutes"
                else:
                    eta = "calculating..."
            else:
                speed_str = "0 B/s"
                eta = "calculating..."
            
            # Update GUI every 10% to avoid flooding chat
            if hasattr(self.client, 'gui') and percent % 10 == 0:
                progress_message = f"Downloading {filename}... {percent}% ({self.format_size(received)} of {self.format_size(filesize)})"
                self.download_progress.emit(filename, received, filesize)
                print(progress_message)
                
            print(f"Progress update: {percent}% ({self.format_size(received)} of {self.format_size(filesize)})")
        
        # Store update function and show initial state
        self.downloads[filename]['update_text'] = update_progress_text
        update_progress_text()
    
    def format_size(self, size_bytes):
        """
        Convert byte count to human-readable size string.
        
        Args:
            size_bytes: File size in bytes
            
        Returns:
            Formatted string (e.g., "1.5 MB", "320.0 KB")
        """
        if size_bytes < 1024:
            return f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
            
    def find_local_file(self, filename):
        """
        Search for a file in uploads directory, common locations, and custom paths.
        Checks file_paths.txt for additional search directories.
        
        Args:
            filename: Name of file to locate
            
        Returns:
            Full path to file if found, None otherwise
        """
        # Check uploads directory first (primary location for shared files)
        uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        uploads_path = os.path.join(uploads_dir, filename)
        
        if os.path.exists(uploads_path):
            print(f"Found file {filename} in uploads directory at {uploads_path}")
            return uploads_path
        
        # Common search locations
        search_paths = [
            os.path.dirname(os.path.abspath(__file__)),
            os.getcwd(),
            os.path.join(os.path.expanduser("~"), "Downloads"),
            os.path.join(os.path.expanduser("~"), "Documents"),
        ]
        
        # Load custom search paths from file_paths.txt (supports ${HOME}, ${DOWNLOADS}, ${CWD} variables)
        try:
            paths_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "file_paths.txt")
            if os.path.exists(paths_file):
                with open(paths_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue  # Skip comments and empty lines
                            
                        # Expand path variables
                        line = line.replace("${HOME}", os.path.expanduser("~"))
                        line = line.replace("${DOWNLOADS}", os.path.join(os.path.expanduser("~"), "Downloads"))
                        line = line.replace("${CWD}", os.getcwd())
                        
                        search_paths.append(line)
        except Exception as e:
            print(f"Error loading custom file paths: {e}")
        
        # Search all paths for the file
        for path in search_paths:
            full_path = os.path.join(path, filename)
            if os.path.exists(full_path):
                print(f"Found file {filename} at {full_path}")
                return full_path
                
        print(f"Could not find file {filename} in any search path")
        return None
    
    def cancel_download(self, filename):
        """
        Cancel an in-progress download and clean up resources.
        
        Args:
            filename: Name of file to cancel
        """
        if filename in self.downloads:
            print(f"Download of {filename} canceled")
            
            # Close file handle
            if 'file' in self.downloads[filename]:
                self.downloads[filename]['file'].close()
            
            # Notify server of cancellation
            cancel_msg = {'type': 'file_cancel', 'filename': filename}
            try:
                send_with_size(self.client.tcp_socket, pickle.dumps(cancel_msg))
            except:
                pass  # Connection may be closed
            
            # Remove from downloads dict
            del self.downloads[filename]
    
    def handle_file_chunk(self, data):
        """
        Process incoming file chunk during download.
        Writes chunk to file, updates progress, and handles completion.
        
        Args:
            data: Pickled payload containing file_chunk or file_end message
        """
        try:
            payload = pickle.loads(data)
            if payload['type'] == 'file_chunk':
                filename = payload['filename']
                chunk = payload.get('chunk')
                
                if not chunk:
                    print(f"WARNING: Received empty chunk for file {filename}")
                    return
                    
                print(f"Received chunk for {filename} of size {len(chunk)} bytes")
                
                # Ignore chunks for files we're not downloading
                if filename not in self.downloads:
                    print(f"Received chunk for file {filename} but we're not downloading it")
                    return
                
                download_info = self.downloads[filename]
                
                # Write chunk and update byte count
                download_info['file'].write(chunk)
                download_info['received'] += len(chunk)
                
                first_chunk = (download_info['received'] == len(chunk))
                
                # Update progress every 256KB or 5% to reduce GUI overhead
                update_needed = first_chunk or \
                               (download_info['received'] % 262144 < len(chunk)) or \
                               (download_info['received'] >= download_info['size']) or \
                               (download_info['received'] * 20 // download_info['size'] > 
                                (download_info['received'] - len(chunk)) * 20 // download_info['size'])
                
                if update_needed:
                    if 'update_text' in download_info:
                        download_info['update_text']()
                    
                    self.download_progress.emit(
                        filename, 
                        download_info['received'], 
                        download_info['size']
                    )
                
                # Log every 1MB for debugging
                if download_info['received'] % 1048576 < len(chunk):
                    percent = int(100 * download_info['received'] / download_info['size'])
                    print(f"Download progress: {filename} - {percent}% ({self.format_size(download_info['received'])} / {self.format_size(download_info['size'])})")
                
            elif payload['type'] == 'file_end':
                # Download complete - finalize and emit signal
                filename = payload['filename']
                
                if filename not in self.downloads:
                    print(f"Received file_end for {filename} but we're not downloading it")
                    return
                    
                download_info = self.downloads[filename]
                
                print(f"Download completed: {filename} - received {self.format_size(download_info['received'])} of {self.format_size(download_info['size'])}")
                
                # Close file and store path
                download_info['file'].close()
                final_path = download_info['path']
                
                # Remove from downloads before emitting to prevent recursion
                del self.downloads[filename]
                
                # Notify GUI of completion
                self.download_complete.emit(filename, final_path)
                
                print(f"Download complete signal emitted for {filename}")
                print(f"Download of {filename} completed")
                
        except (pickle.UnpicklingError, KeyError, IOError) as e:
            print(f"Error handling file chunk: {e}")
            # Clean up failed download
            filename = payload.get('filename')
            if filename and filename in self.downloads:
                self.cancel_download(filename)
                    
    def handle_file_request(self, payload):
        """
        Process request from another client to download one of our shared files.
        Locates file and initiates transfer via send_file_to_requester.
        
        Args:
            payload: Dict containing filename and requester info
        """
        filename = payload.get('filename')
        requester = payload.get('requester')
        
        if not filename or not requester:
            print(f"Invalid file request: missing filename or requester")
            return
            
        print(f"Received request for file {filename} from another client")
        
        # Check uploads directory first (primary location for shared files)
        uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
        uploads_path = os.path.join(uploads_dir, filename)
        
        if os.path.exists(uploads_path):
            print(f"Found file {filename} in uploads directory")
            self.send_file_to_requester(uploads_path, filename, requester)
            return
        
        # Search other locations
        local_filepath = self.find_local_file(filename)
        
        if not local_filepath:
            # Send error to requester
            print(f"Error: Cannot find file {filename} to send to requester")
            error_msg = {
                'type': 'file_error',
                'message': f"File owner could not locate the file",
                'filename': filename,
                'requester': requester
            }
            send_with_size(self.client.tcp_socket, pickle.dumps(error_msg))
            return
            
        # Initiate file transfer
        self.send_file_to_requester(local_filepath, filename, requester)
        
    def send_file_to_requester(self, filepath, filename, requester):
        """
        Send file in chunks to a requesting client via server.
        Runs in background thread - no GUI operations to avoid threading issues.
        
        Args:
            filepath: Full path to file on disk
            filename: Name of file being sent
            requester: Client ID requesting the file
        """
        filesize = os.path.getsize(filepath)
        
        print(f"Sending file {filename} ({self.format_size(filesize)}) to requester")
        
        # No progress dialog - this runs in background thread
        progress = None
        
        try:
            start_time = time.time()
            sent_bytes = 0
            
            # Read and send file in chunks
            with open(filepath, 'rb', buffering=8192) as f:
                chunk_size = FILE_CHUNK_SIZE
                
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break  # EOF
                    if progress and progress.wasCanceled():
                        print("File sending cancelled.")
                        return
                        
                    # Send chunk to server with requester ID
                    data = {
                        'type': 'file_chunk',
                        'filename': filename,
                        'chunk': chunk,
                        'requester': requester  # Routes chunk to correct client
                    }
                    send_with_size(self.client.tcp_socket, pickle.dumps(data))
                    sent_bytes += len(chunk)
                    
                    # Update progress dialog if present
                    if progress:
                        progress.setValue(sent_bytes)
                        
                        if sent_bytes % 262144 < chunk_size:  # Update every 256KB
                            percent = int(100 * sent_bytes / filesize)
                            elapsed = time.time() - start_time
                            if elapsed > 0:
                                speed = sent_bytes / elapsed
                                speed_str = self.format_size(speed) + "/s"
                                progress.setLabelText(
                                    f"Sending {filename} to another client...\n"
                                    f"{percent}% complete ({self.format_size(sent_bytes)} of {self.format_size(filesize)})\n"
                                    f"Speed: {speed_str}"
                                )
            
            # Send completion marker
            eof_marker = {
                'type': 'file_end',
                'filename': filename,
                'requester': requester
            }
            send_with_size(self.client.tcp_socket, pickle.dumps(eof_marker))
            print(f"Finished sending {filename} to requester")
            
        except Exception as e:
            print(f"Error sending file to requester: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if progress:
                progress.close()