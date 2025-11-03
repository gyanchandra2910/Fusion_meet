"""
FusionMeet Main GUI Module.
Provides the main application window with video grid, controls, chat, and file sharing.
"""

import os
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                          QTextEdit, QLineEdit, QLabel, QGridLayout, QFrame, QMessageBox, 
                          QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt5.QtGui import QIcon, QFont, QPixmap
from PyQt5.QtCore import Qt, QSize, QTimer, pyqtSlot

from config import *
from utils import resource_path

from screen_sharing_module import ScreenShareDisplay
from file_dialog import SharedFilesDialog
from join_media_dialog import JoinMediaDialog

class MainWindow(QMainWindow):
    """Main application window for FusionMeet video conferencing."""
    
    def __init__(self, client, username):
        """
        Initialize main window with video grid, controls, and side panels.
        
        Args:
            client: Client instance managing network connections
            username: Display name for current user
        """
        super().__init__()
        self.client = client
        self.username = username
        self.setWindowTitle(f"FusionMeet - {username}")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet(f"background-color: {APP_BG_COLOR};")
        
        # Track user join status and media preferences
        self.has_joined_call = False
        self.initial_camera_preference = False
        self.initial_mic_preference = False
        
        # Light-themed message box style for better readability
        self.dialog_style = """
            QMessageBox {
                background-color: #FFFFFF;
                border: 1px solid #CCCCCC;
                border-radius: 6px;
            }
            QMessageBox QLabel {
                color: #000000;
                font-size: 13px;
                font-weight: 500;
                min-width: 300px;
            }
            QMessageBox QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover {
                background-color: #45a049;
            }
        """
        
        self.files_dialog = None
        
        # Connect file sharing signals for notifications
        try:
            if hasattr(self.client.file_sharing_handler, 'new_file_available'):
                print("Connecting new_file_available signal")
                self.client.file_sharing_handler.new_file_available.connect(self.on_new_file_available)
            else:
                print("WARNING: new_file_available signal not found")
                
            if hasattr(self.client.file_sharing_handler, 'download_complete'):
                print("Connecting download_complete signal")
                self.client.file_sharing_handler.download_complete.connect(self.on_download_complete)
            else:
                print("WARNING: download_complete signal not found")
                
            if hasattr(self.client.file_sharing_handler, 'download_progress'):
                print("Connecting download_progress signal")
                self.client.file_sharing_handler.download_progress.connect(self.on_download_progress)
            else:
                print("WARNING: download_progress signal not found")
        except Exception as e:
            print(f"Could not connect file sharing signals: {e}")
            import traceback
            traceback.print_exc()

        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        
        # Create main vertical layout to hold content and controls
        main_vertical_layout = QVBoxLayout(self.main_widget)
        main_vertical_layout.setContentsMargins(10, 10, 10, 5)  # Reduced bottom margin
        main_vertical_layout.setSpacing(5)  # Reduced spacing
        
        # Create horizontal content container
        content_widget = QWidget()
        self.layout = QHBoxLayout(content_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(10)
        
        main_vertical_layout.addWidget(content_widget)
        
        # FIXED: Connect presenter status signal to update button state
        try:
            if hasattr(self.client.screen_share_handler, 'presenter_status_changed'):
                print("Connecting presenter_status_changed signal")
                self.client.screen_share_handler.presenter_status_changed.connect(
                    self.update_screen_share_button
                )
            else:
                print("WARNING: presenter_status_changed signal not found")
        except Exception as e:
            print(f"Could not connect presenter status signal: {e}")
            import traceback
            traceback.print_exc()
        
        # Connect participants changed signal to update participants list
        try:
            if hasattr(self.client, 'video_handler') and hasattr(self.client.video_handler, 'participants_changed_signal'):
                print("Connecting participants_changed signal")
                self.client.video_handler.participants_changed_signal.connect(
                    self.update_participants_list
                )
            else:
                print("WARNING: participants_changed_signal not found")
        except Exception as e:
            print(f"Could not connect participants signal: {e}")
            import traceback
            traceback.print_exc()
        
        # Initialize the shared files list
        self.shared_files_widget = None

        # Left panel for video grid
        self.video_panel = QWidget()
        self.video_panel.setStyleSheet(f"background-color: #1a1a1a; border-radius: 10px;")
        self.video_panel.setMinimumWidth(640)  # Set minimum width for video panel
        
        # Use a grid layout with fixed spacing and margins
        self.video_layout = QGridLayout(self.video_panel)
        self.video_layout.setSpacing(10)  # Space between videos
        self.video_layout.setContentsMargins(10, 10, 10, 10)  # Margins inside panel
        
        # Make sure rows and columns have equal size cells
        for i in range(2):  # Set up for 2x2 grid
            self.video_layout.setRowMinimumHeight(i, 240)  # Match VideoWidget height
            self.video_layout.setColumnMinimumWidth(i, 320)  # Match VideoWidget width
        
        self.placeholder_label = QLabel("Waiting for video streams...")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setFont(QFont("Arial", 16))
        self.placeholder_label.setStyleSheet(f"color: {TEXT_COLOR};")
        self.video_layout.addWidget(self.placeholder_label, 0, 0)

        self.layout.addWidget(self.video_panel, 7)

        # Screen share display (hidden by default)
        self.screen_share_display = None

        # Right panel for participants, files, and chat
        self.right_panel = QWidget()
        self.right_panel.setStyleSheet(f"background-color: #1a1a1a; border-radius: 10px;")
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(10, 10, 10, 10)
        self.layout.addWidget(self.right_panel, 3)
        
        # Setup participants panel (at top)
        self.setup_participants_panel()
        
        # Setup shared files panel (middle)
        self.setup_files_panel()
        
        # Setup chat panel (below files)
        self.setup_chat_panel()
        
        # Setup control buttons (at bottom center of main window)
        self.setup_controls()

    def remove_video_widget(self, widget):
        """
        Remove video widget from grid and show placeholder if grid becomes empty.
        
        Args:
            widget: Video widget to remove from layout
        """
        self.video_layout.removeWidget(widget)
        widget.hide()
        widget.setParent(None)
        
        # Update participants list
        self.update_participants_list()
        
        # Show placeholder if no videos remain
        has_videos = False
        for i in range(self.video_layout.count()):
            item = self.video_layout.itemAt(i)
            if item and item.widget() and item.widget().isVisible():
                has_videos = True
                break
                
        if not has_videos:
            self.placeholder_label = QLabel("Waiting for video streams...")
            self.placeholder_label.setAlignment(Qt.AlignCenter)
            self.placeholder_label.setFont(QFont("Arial", 16))
            self.placeholder_label.setStyleSheet(f"color: white;")
            self.video_layout.addWidget(self.placeholder_label, 0, 0)

    def show_screen_share(self, widget):
        """
        Display screen share widget in main area, hiding video grid.
        
        Args:
            widget: Screen share display widget
        """
        self.video_panel.hide()
        # Remove widget from previous parent if needed
        if widget.parent():
            widget.parent().layout().removeWidget(widget)
        self.layout.insertWidget(0, widget, 7)
        widget.show()

    def hide_screen_share(self):
        """Hide screen share display and restore video grid."""
        if self.screen_share_display:
            self.screen_share_display.hide()
            self.layout.removeWidget(self.screen_share_display)
            self.screen_share_display.deleteLater()
            self.screen_share_display = None
        self.video_panel.show()

    def setup_controls(self):
        """Create bottom control bar with media toggle and join buttons."""
        # Control buttons frame at bottom center
        self.controls_frame = QFrame()
        self.controls_frame.setStyleSheet("background-color: #2a2a2a; border-radius: 8px; padding: 5px;")
        self.controls_layout = QHBoxLayout(self.controls_frame)
        self.controls_layout.setSpacing(15)
        self.controls_layout.setContentsMargins(8, 5, 8, 5)
        
        button_style = ("QPushButton { "
                   "background-color: #333333; "
                   "color: #FFFFFF; "
                   "border-radius: 20px; "
                   "border: none; "
                   "padding: 8px; "
                   "min-width: 45px; "
                   "min-height: 45px; "
                   "} "
                   "QPushButton:hover { "
                   "background-color: #444444; "
                   "} "
                   "QPushButton:pressed { "
                   "background-color: #555555; "
                   "}")
        
        label_style = """
            QLabel {
                color: white;
                font-size: 11px;
                font-weight: bold;
                margin-top: 3px;
            }
        """
        
        # Create control buttons with icons and labels
        
        # Join Conference button (shown initially before joining)
        join_container = QWidget()
        join_layout = QVBoxLayout(join_container)
        join_layout.setContentsMargins(0, 0, 0, 0)
        join_layout.setAlignment(Qt.AlignCenter)
        
        self.join_conference_button = QPushButton("📞 Join Conference")
        self.join_conference_button.setStyleSheet(
            button_style + """
            QPushButton {
                background-color: #4CAF50;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            """
        )
        self.join_conference_button.setToolTip("Join the conference call")
        self.join_conference_button.clicked.connect(self.handle_join_conference)
        
        join_layout.addWidget(self.join_conference_button, alignment=Qt.AlignCenter)
        
        # Video button with label
        video_container = QWidget()
        video_layout = QVBoxLayout(video_container)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setAlignment(Qt.AlignCenter)
        
        self.video_button = QPushButton()
        self.video_button.setStyleSheet(button_style)
        self.video_button.setIcon(QIcon(resource_path("icons/video_on.png")))
        self.video_button.setIconSize(QSize(30, 30))
        self.video_button.setToolTip("Toggle Video")
        self.video_button.clicked.connect(self.toggle_video)
        
        video_label = QLabel("Video")
        video_label.setStyleSheet(label_style)
        video_label.setAlignment(Qt.AlignCenter)
        
        video_layout.addWidget(self.video_button, alignment=Qt.AlignCenter)
        video_layout.addWidget(video_label, alignment=Qt.AlignCenter)
        
        # Audio button with label and level indicator
        audio_container = QWidget()
        audio_layout = QVBoxLayout(audio_container)
        audio_layout.setContentsMargins(0, 0, 0, 0)
        audio_layout.setAlignment(Qt.AlignCenter)
        
        # Add an audio level indicator
        self.audio_level_indicator = QFrame()
        self.audio_level_indicator.setFixedSize(50, 5)
        self.audio_level_indicator.setStyleSheet("background-color: #333333; border-radius: 2px;")
        
        # Add a colored bar inside to show the level
        self.audio_level_bar = QFrame(self.audio_level_indicator)
        self.audio_level_bar.setFixedHeight(5)
        self.audio_level_bar.setFixedWidth(0)  # Start with zero width
        self.audio_level_bar.setStyleSheet("background-color: #4CAF50; border-radius: 2px;")
        
        self.mute_button = QPushButton()
        self.mute_button.setStyleSheet(button_style)
        self.mute_button.setIcon(QIcon(resource_path("icons/mic_on.png")))
        self.mute_button.setIconSize(QSize(30, 30))
        self.mute_button.setToolTip("Toggle Audio")
        self.mute_button.clicked.connect(self.toggle_mute)
        
        audio_label = QLabel("Microphone")
        audio_label.setStyleSheet(label_style)
        audio_label.setAlignment(Qt.AlignCenter)
        
        audio_layout.addWidget(self.mute_button, alignment=Qt.AlignCenter)
        audio_layout.addWidget(audio_label, alignment=Qt.AlignCenter)
        
        # Screen share button with label
        screen_container = QWidget()
        screen_layout = QVBoxLayout(screen_container)
        screen_layout.setContentsMargins(0, 0, 0, 0)
        screen_layout.setAlignment(Qt.AlignCenter)
        
        self.share_screen_button = QPushButton()
        self.share_screen_button.setStyleSheet(button_style)
        self.share_screen_button.setIcon(QIcon(resource_path("icons/screen_share.png")))
        self.share_screen_button.setIconSize(QSize(30, 30))
        self.share_screen_button.setToolTip("Share Screen")
        self.share_screen_button.clicked.connect(self.toggle_screen_share)
        
        # FIXED: Store original button style for enabling/disabling
        self.screen_share_btn_original_style = button_style
        
        screen_label = QLabel("Screen Share")
        screen_label.setStyleSheet(label_style)
        screen_label.setAlignment(Qt.AlignCenter)
        
        screen_layout.addWidget(self.share_screen_button, alignment=Qt.AlignCenter)
        screen_layout.addWidget(screen_label, alignment=Qt.AlignCenter)
        
        # File button with label
        file_container = QWidget()
        file_layout = QVBoxLayout(file_container)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setAlignment(Qt.AlignCenter)
        
        self.file_button = QPushButton()
        self.file_button.setStyleSheet(button_style)
        self.file_button.setIcon(QIcon(resource_path("icons/file_transfer.png")))
        self.file_button.setIconSize(QSize(30, 30))
        self.file_button.setToolTip("Share File")
        self.file_button.clicked.connect(self.share_file)
        
        file_label = QLabel("Share File")
        file_label.setStyleSheet(label_style)
        file_label.setAlignment(Qt.AlignCenter)
        
        file_layout.addWidget(self.file_button, alignment=Qt.AlignCenter)
        file_layout.addWidget(file_label, alignment=Qt.AlignCenter)
        
        # Leave button with label
        leave_container = QWidget()
        leave_layout = QVBoxLayout(leave_container)
        leave_layout.setContentsMargins(0, 0, 0, 0)
        leave_layout.setAlignment(Qt.AlignCenter)
        
        self.leave_button = QPushButton()
        self.leave_button.setStyleSheet(button_style + "background-color: #FF5252;")
        self.leave_button.setIcon(QIcon(resource_path("icons/leave.png")))
        self.leave_button.setIconSize(QSize(30, 30))
        self.leave_button.setToolTip("Leave Meeting")
        self.leave_button.clicked.connect(self.close)
        
        leave_label = QLabel("Leave")
        leave_label.setStyleSheet(label_style)
        leave_label.setAlignment(Qt.AlignCenter)
        
        leave_layout.addWidget(self.leave_button, alignment=Qt.AlignCenter)
        leave_layout.addWidget(leave_label, alignment=Qt.AlignCenter)
        
        # Add button containers to layout
        self.controls_layout.addWidget(join_container)
        self.controls_layout.addWidget(video_container)
        self.controls_layout.addWidget(audio_container)
        self.controls_layout.addWidget(screen_container)
        self.controls_layout.addWidget(file_container)
        self.controls_layout.addWidget(leave_container)
        
        # Store container references for visibility management
        self.join_container = join_container
        self.video_container = video_container
        self.audio_container = audio_container
        
        # Initially show only Join Conference button
        self.join_container.setVisible(True)
        self.video_container.setVisible(False)
        self.audio_container.setVisible(False)
        
        # Add control buttons to bottom center of main window
        # Create a bottom controls container
        bottom_controls_container = QWidget()
        bottom_controls_layout = QHBoxLayout(bottom_controls_container)
        bottom_controls_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        bottom_controls_layout.addStretch(1)
        bottom_controls_layout.addWidget(self.controls_frame)
        bottom_controls_layout.addStretch(1)
        
        # Add to main vertical layout (access through parent)
        self.main_widget.layout().addWidget(bottom_controls_container)
    
    def setup_participants_panel(self):
        """Create participants list panel showing connected users."""
        # Participants panel container
        participants_container = QWidget()
        participants_layout = QVBoxLayout(participants_container)
        participants_layout.setContentsMargins(0, 0, 0, 10)
        participants_layout.setSpacing(5)
        
        # Panel title
        participants_title = QLabel("Participants")
        participants_title.setFont(QFont("Arial", 14, QFont.Bold))
        participants_title.setStyleSheet(f"color: {TEXT_COLOR}; margin-bottom: 5px;")
        participants_title.setAlignment(Qt.AlignCenter)
        participants_layout.addWidget(participants_title)
        
        # Scrollable list for participants
        from PyQt5.QtWidgets import QScrollArea, QListWidget
        self.participants_list = QListWidget()
        self.participants_list.setMaximumHeight(120)
        self.participants_list.setStyleSheet(f"""
            QListWidget {{
                background-color: #2a2a2a;
                color: {TEXT_COLOR};
                border-radius: 5px;
                padding: 5px;
                font-size: 12px;
            }}
            QListWidget::item {{
                padding: 5px;
                border-radius: 3px;
            }}
            QListWidget::item:hover {{
                background-color: #333333;
            }}
        """)
        participants_layout.addWidget(self.participants_list)
        
        # Add the participants panel to the right layout
        self.right_layout.addWidget(participants_container)
        
        # Initialize with current user
        self.update_participants_list()
    
    @pyqtSlot()
    def update_participants_list(self):
        """
        Update participants list from connected users (thread-safe).
        Aggregates participants from client.participants and video_handler.
        """
        try:
            self.participants_list.clear()
            
            # Collect unique participants from multiple sources
            participants = set()
            participants.add(self.username)  # Add yourself first
            
            # Add from client's tracked participants
            if hasattr(self.client, 'participants'):
                participants.update(self.client.participants)
                print(f"🔍 Participants from client.participants: {self.client.participants}")
            
            # Add users with active video streams
            if hasattr(self.client, 'video_handler'):
                if hasattr(self.client.video_handler, 'remote_video_widgets'):
                    video_users = list(self.client.video_handler.remote_video_widgets.keys())
                    participants.update(video_users)
                    print(f"🔍 Participants from video widgets: {video_users}")
            
            # Filter out invalid entries
            participants = {p for p in participants if p and p != "creating"}
            
            # Display: current user first, then others alphabetically
            self.participants_list.addItem(f"👤 {self.username} (You)")
            for username in sorted(participants - {self.username}):
                self.participants_list.addItem(f"👤 {username}")
            
            print(f"🔄 Participants list updated: {sorted(participants)}")
            
        except Exception as e:
            print(f"Error updating participants list: {e}")
    
    def setup_files_panel(self):
        """Create shared files panel with file table and action buttons."""
        # Files panel container
        files_container = QWidget()
        files_layout = QVBoxLayout(files_container)
        files_layout.setContentsMargins(0, 0, 0, 10)
        files_layout.setSpacing(5)
        
        # Panel title
        files_title = QLabel("Shared Files")
        files_title.setFont(QFont("Arial", 14, QFont.Bold))
        files_title.setStyleSheet(f"color: {TEXT_COLOR}; margin-bottom: 5px;")
        files_title.setAlignment(Qt.AlignCenter)
        files_layout.addWidget(files_title)
        
        # File list table (name, size, download button)
        self.files_table = QTableWidget(0, 3)
        self.files_table.setHorizontalHeaderLabels(["File Name", "Size", "Action"])
        self.files_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.files_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.files_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.files_table.verticalHeader().setVisible(False)
        self.files_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.files_table.setMaximumHeight(120)
        self.files_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: #2a2a2a;
                color: {TEXT_COLOR};
                border-radius: 5px;
                gridline-color: #333333;
            }}
            QHeaderView::section {{
                background-color: #333333;
                color: {TEXT_COLOR};
                padding: 5px;
                border: none;
                font-weight: bold;
            }}
        """)
        files_layout.addWidget(self.files_table)
        
        # Add buttons
        buttons_layout = QHBoxLayout()
        
        # Share button
        share_button = QPushButton("📁 Share New File")
        share_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d7;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1e88e5;
            }
        """)
        share_button.clicked.connect(self.share_new_file)
        buttons_layout.addWidget(share_button)
        
        # Refresh button
        refresh_button = QPushButton("🔄 Refresh")
        refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        refresh_button.clicked.connect(self.refresh_files)
        buttons_layout.addWidget(refresh_button)
        
        files_layout.addLayout(buttons_layout)
        
        # Add the files panel to the right layout
        self.right_layout.addWidget(files_container)
        
        # Initialize with any existing files
        self.refresh_files()
    
    def setup_chat_panel(self):
        """Create group chat panel with message history and input field."""
        # Panel title
        chat_label = QLabel("Group Chat")
        chat_label.setFont(QFont("Arial", 14, QFont.Bold))
        chat_label.setStyleSheet(f"color: {TEXT_COLOR}; margin-bottom: 5px;")
        chat_label.setAlignment(Qt.AlignCenter)
        
        # Message history display (read-only, supports HTML)
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setStyleSheet(f"""
            QTextEdit {{
                background-color: #2a2a2a;
                color: {TEXT_COLOR};
                border-radius: 5px;
                padding: 8px;
                border: 1px solid #333333;
            }}
        """)
        self.chat_history.setTextInteractionFlags(Qt.TextBrowserInteraction)
        
        # Chat input area
        chat_input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #333333;
                color: {TEXT_COLOR};
                border-radius: 5px;
                padding: 10px;
                border: 1px solid #444444;
            }}
            QLineEdit:focus {{
                border: 1px solid #00BFFF;
            }}
        """)
        self.chat_input.setPlaceholderText("Type a message...")
        self.chat_input.returnPressed.connect(self.send_chat_message)
        
        send_button = QPushButton("➤")
        send_button.setStyleSheet("""
            QPushButton {
                background-color: #00BFFF;
                color: white;
                border-radius: 5px;
                padding: 10px 15px;
                font-size: 16px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #0099CC;
            }
            QPushButton:pressed {
                background-color: #007ACC;
            }
        """)
        send_button.clicked.connect(self.send_chat_message)
        
        chat_input_layout.addWidget(self.chat_input)
        chat_input_layout.addWidget(send_button)
        
        # Add chat components to the right panel
        self.right_layout.addWidget(chat_label)
        self.right_layout.addWidget(self.chat_history, 1)  # Give chat more stretch
        self.right_layout.addLayout(chat_input_layout)
        
    def share_file(self):
        """Open file picker to share a file (wrapper for share_new_file)."""
        self.share_new_file()
    
    def share_new_file(self):
        """Initiate file sharing process via file_sharing_handler."""
        try:
            print("Starting file sharing process")
            self.client.file_sharing_handler.send_file()
            print("File sharing process completed")
        except AttributeError as e:
            print(f"AttributeError in share_new_file: {e}")
            filepath, _ = QFileDialog.getOpenFileName(self, "Select File to Share")
            if filepath:
                filename = os.path.basename(filepath)
                print(f"Selected file: {filename}")
        except Exception as e:
            print(f"Error sharing file: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to share file: {str(e)}")
        
        # Refresh the files list
        print("Refreshing files list after sharing")
        self.refresh_files()
        
    def send_chat_message(self):
        """Send typed chat message and display in local chat history."""
        message = self.chat_input.text()
        if message:
            self.client.chat_handler.send_message(message)
            self.chat_input.clear()
            self.add_chat_message(self.username, message)

    def handle_join_conference(self):
        """
        Show join dialog and start selected media streams.
        User chooses initial camera/mic state before joining.
        """
        dialog = JoinMediaDialog(self)
        if dialog.exec_() == JoinMediaDialog.Accepted:
            camera_enabled, mic_enabled = dialog.get_selections()
            self.has_joined_call = True
            self.initial_camera_preference = camera_enabled
            self.initial_mic_preference = mic_enabled
            
            # Switch from join button to media controls
            self.join_container.setVisible(False)
            self.video_container.setVisible(True)
            self.audio_container.setVisible(True)
            
            # Start microphone if enabled
            if mic_enabled:
                try:
                    result = self.client.audio_handler.start_stream()
                    if result:
                        self.mute_button.setIcon(QIcon(resource_path("icons/mic_on.png")))
                        self.mute_button.setToolTip("Click to stop microphone")
                        
                        # Start audio level visualization timer
                        if not hasattr(self, 'audio_level_timer') or not self.audio_level_timer:
                            self.audio_level_timer = QTimer()
                            self.audio_level_timer.timeout.connect(self.update_audio_level)
                            self.audio_level_timer.start(100)
                        
                        self.client.audio_handler.audio_status_changed.connect(self.handle_audio_status_change)
                except Exception as e:
                    print(f"Error starting audio: {str(e)}")
            
            # Start camera if enabled
            if camera_enabled:
                try:
                    result = self.client.video_handler.start_stream()
                    if result:
                        self.video_button.setIcon(QIcon(resource_path("icons/video_on.png")))
                except Exception as e:
                    print(f"Error starting video: {str(e)}")

    def toggle_mute(self):
        """Toggle microphone on/off and update UI icon."""
        if not self.client.audio_handler:
            print("Error: Audio handler not initialized")
            return
        
        try:
            if self.client.audio_handler.is_streaming:
                # Stop microphone
                print("🔇 Stopping microphone...")
                self.client.audio_handler.stop_stream()
                self.mute_button.setIcon(QIcon(resource_path("icons/mic_off.png")))
                self.mute_button.setToolTip("Click to start microphone")
                if hasattr(self, 'audio_level_timer') and self.audio_level_timer:
                    self.audio_level_timer.stop()
            else:
                # Start microphone
                print("🎤 Starting microphone...")
                result = self.client.audio_handler.start_stream()
                if result:
                    self.mute_button.setIcon(QIcon(resource_path("icons/mic_on.png")))
                    self.mute_button.setToolTip("Click to stop microphone")
                    
                    # Start audio level visualization (10 Hz update)
                    if not hasattr(self, 'audio_level_timer') or not self.audio_level_timer:
                        self.audio_level_timer = QTimer()
                        self.audio_level_timer.timeout.connect(self.update_audio_level)
                        self.audio_level_timer.start(100)
                        
                    self.client.audio_handler.audio_status_changed.connect(self.handle_audio_status_change)
        except Exception as e:
            print(f"Error toggling microphone: {str(e)}")

    def toggle_video(self):
        """Toggle camera on/off and update UI icon."""
        if not self.client.video_handler:
            print("Error: Video handler not initialized")
            return
        
        try:
            if self.client.video_handler.is_streaming:
                self.client.video_handler.stop_stream()
                self.video_button.setIcon(QIcon(resource_path("icons/video_off.png")))
            else:
                result = self.client.video_handler.start_stream()
                if result:
                    self.video_button.setIcon(QIcon(resource_path("icons/video_on.png")))
        except Exception as e:
            print(f"Error toggling video: {str(e)}")

    def toggle_screen_share(self):
        """Toggle screen sharing on/off and update UI."""
        if not self.client.screen_share_handler:
            print("Error: Screen share handler not initialized")
            return
            
        try:
            # Prevent multiple clicks during toggle
            self.share_screen_button.setEnabled(False)
            
            if self.client.screen_share_handler.is_sharing:
                # Stop sharing
                print("Stopping screen sharing...")
                self.client.screen_share_handler.stop_sharing()
                self.share_screen_button.setIcon(QIcon(resource_path("icons/screen_share.png")))
                self.client.screen_share_handler.hide_screen_share_signal.emit()
            else:
                # Start sharing
                print("Starting screen sharing...")
                result = self.client.screen_share_handler.start_sharing()
                if result:
                    self.share_screen_button.setIcon(QIcon(resource_path("icons/screen_share_off.png")))
                    print("Screen sharing started successfully")
                else:
                    print("Failed to start screen sharing")
        except Exception as e:
            print(f"Error toggling screen share: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            self.share_screen_button.setEnabled(True)

    @pyqtSlot(str, str)
    def add_chat_message(self, sender, message):
        """
        Add message to chat history with HTML formatting (thread-safe).
        
        Args:
            sender: Username of message sender
            message: Message text (may contain HTML)
        """
        # Replace "You" with actual username
        if sender == "You":
            sender = self.username
            
        # Format the message with sender's name
        self.chat_history.append(f"<b>{sender}:</b> {message}")
        
        # Auto-scroll to the bottom to show new messages
        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def refresh_files(self):
        """Update files table with currently available shared files."""
        self.files_table.setRowCount(0)
        
        try:
            # Get files from file sharing handler
            if not hasattr(self.client.file_sharing_handler, 'files'):
                print("File sharing handler has no 'files' attribute")
                return
                
            files = self.client.file_sharing_handler.files
            print(f"Refreshing files list. Files available: {len(files)}")
            print(f"Files: {files}")
            
            # Show "No files" message if empty
            if len(files) == 0:
                self.files_table.setRowCount(1)
                no_files = QTableWidgetItem("No shared files available")
                no_files.setTextAlignment(Qt.AlignCenter)
                no_files.setFlags(Qt.ItemIsEnabled)
                self.files_table.setSpan(0, 0, 1, 3)  # Span all columns
                self.files_table.setItem(0, 0, no_files)
                return
            
            # Populate table with available files
            for row, (filename, filesize) in enumerate(files.items()):
                self.files_table.insertRow(row)
                print(f"Adding file to table: {filename} ({self.format_size(filesize)})")
                
                # Filename column
                name_item = QTableWidgetItem(filename)
                name_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self.files_table.setItem(row, 0, name_item)
                
                # Size column
                size_str = self.format_size(filesize)
                size_item = QTableWidgetItem(size_str)
                size_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                size_item.setTextAlignment(Qt.AlignCenter)
                self.files_table.setItem(row, 1, size_item)
                
                # Download button
                download_btn = QPushButton("Download")
                download_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; border: none; padding: 5px 10px; border-radius: 3px; } "
                                           "QPushButton:hover { background-color: #45a049; }")
                download_btn.clicked.connect(lambda _, f=filename: self.download_file(f))
                
                self.files_table.setCellWidget(row, 2, download_btn)
                
            self.files_table.update()
        except Exception as e:
            import traceback
            print(f"Error refreshing files: {e}")
            traceback.print_exc()
    
    def download_file(self, filename):
        """
        Initiate file download and update UI to show progress.
        
        Args:
            filename: Name of file to download
        """
        try:
            # Update download button to show 0% progress
            for row in range(self.files_table.rowCount()):
                if self.files_table.item(row, 0) and self.files_table.item(row, 0).text() == filename:
                    download_btn = self.files_table.cellWidget(row, 2)
                    if download_btn:
                        download_btn.setText("0%")
                        download_btn.setEnabled(True)
                        download_btn.setStyleSheet("QPushButton { background-color: #007bff; color: white; border: none; padding: 5px 10px; border-radius: 3px; }")
                    break
            
            # Show download notification in chat
            self.add_chat_message("System", f"Downloading <b>{filename}</b>...")
            
            # Start download
            self.client.file_sharing_handler.request_download(filename)
        except Exception as e:
            error_msg = str(e)
            self.add_chat_message("System", f"Download error: {error_msg}")
            self.show_message_box("Download Error", f"Failed to download file: {error_msg}", "critical")
            self.refresh_files()
    
    def show_files_dialog(self):
        """Obsolete: Files now shown in integrated UI panel."""
        self.refresh_files()
        
    def on_new_file_available(self, filename, filesize):
        """
        Handle new file availability notification and update UI.
        
        Args:
            filename: Name of newly available file
            filesize: Size in bytes
        """
        self.add_chat_message("System", f"New file available: <b>{filename}</b> ({self.format_size(filesize)}) - See Shared Files panel to download")
        print(f"New file available signal received: {filename} ({self.format_size(filesize)})")
        self.refresh_files()
        
    def on_download_complete(self, filename, path):
        """
        Handle download completion, show notification, and reset button.
        
        Args:
            filename: Name of downloaded file
            path: Full path where file was saved
        """
        # Prevent duplicate notifications using completed downloads tracker
        if not hasattr(self, '_completed_downloads'):
            self._completed_downloads = set()
            
        if filename not in self._completed_downloads:
            self.add_chat_message("System", f"File <b>{filename}</b> downloaded successfully!")
            self._completed_downloads.add(filename)
            
            # Reset download button to original state
            for row in range(self.files_table.rowCount()):
                if self.files_table.item(row, 0) and self.files_table.item(row, 0).text() == filename:
                    download_btn = self.files_table.cellWidget(row, 2)
                    if download_btn:
                        download_btn.setText("Download")
                        download_btn.setEnabled(True)
                        download_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; border: none; padding: 5px 10px; border-radius: 3px; } "
                                                  "QPushButton:hover { background-color: #45a049; }")
                    break
            
            # Show success dialog
            self.show_message_box(
                "Download Complete", 
                f"The file {filename} has been downloaded successfully to:\n{path}",
                "information"
            )
            
            # Clear from tracker after 5s to allow future downloads
            QTimer.singleShot(5000, lambda: self._completed_downloads.discard(filename))
        
    def on_download_progress(self, filename, received, total):
        """
        Update download progress button with percentage.
        
        Args:
            filename: File being downloaded
            received: Bytes received so far
            total: Total file size in bytes
        """
        percent = int(100 * received / total) if total > 0 else 0
        
        # Update download button progress
        for row in range(self.files_table.rowCount()):
            if self.files_table.item(row, 0) and self.files_table.item(row, 0).text() == filename:
                download_btn = self.files_table.cellWidget(row, 2)
                if download_btn:
                    if percent < 100:
                        download_btn.setText(f"{percent}%")
                    else:
                        download_btn.setText("Complete")
                        download_btn.setStyleSheet("QPushButton { background-color: #28a745; color: white; border: none; padding: 5px 10px; border-radius: 3px; }")
                break
                
        # Show progress notification at 50%
        if percent == 50 and received > 0 and received < total:
            self.add_chat_message("System", f"Download of {filename} is 50% complete")
        
    def format_size(self, size):
        """
        Convert bytes to human-readable size string.
        
        Args:
            size: File size in bytes
            
        Returns:
            Formatted string (e.g., "1.5 MB")
        """
        if size < 1024:
            return f"{size} B"
        elif size < 1024*1024:
            return f"{size/1024:.1f} KB"
        elif size < 1024*1024*1024:
            return f"{size/(1024*1024):.1f} MB"
        else:
            return f"{size/(1024*1024*1024):.1f} GB"
            
    def handle_chat_link(self):
        """Obsolete: Kept as stub for reference."""
        pass
        
    def style_default_message_box(self, msg_box):
        """
        Apply consistent light theme styling to message boxes.
        
        Args:
            msg_box: QMessageBox instance to style
        """
        msg_box.setStyleSheet(self.dialog_style)

    def add_video_widget(self, widget, row, col):
        """
        Add video widget to grid at specified position.
        Removes placeholder if this is first video.
        
        Args:
            widget: Video display widget to add
            row: Grid row position
            col: Grid column position
        """
        # Remove placeholder when first video added
        if hasattr(self, 'placeholder_label') and self.placeholder_label:
            self.placeholder_label.hide()
            self.video_layout.removeWidget(self.placeholder_label)
            self.placeholder_label.deleteLater()
            self.placeholder_label = None
            
        # Detach from previous parent if needed
        if widget.parent():
            widget.parent().layout().removeWidget(widget)
            
        # Add to grid at specified position
        self.video_layout.addWidget(widget, row, col)
        
        # Fixed size for consistent grid appearance
        widget.setMaximumSize(320, 240)
        widget.setMinimumSize(320, 240)
        
        self.update_participants_list()
        widget.show()

    def show_screen_share(self, widget):
        """
        Display screen share in full view, hiding video grid.
        
        Args:
            widget: Screen share display widget
        """
        self.video_panel.hide()
        if widget.parent():
            widget.parent().layout().removeWidget(widget)
        self.layout.insertWidget(0, widget, 7)
        self.screen_share_display = widget
        widget.show()

    def hide_screen_share(self):
        """Hide screen share display and restore video grid."""
        if self.screen_share_display:
            self.screen_share_display.hide()
            self.layout.removeWidget(self.screen_share_display)
            self.screen_share_display.deleteLater()
            self.screen_share_display = None
        self.video_panel.show()


    def update_audio_level(self):
        """Update audio level indicator bar based on current microphone input."""
        if not hasattr(self.client, 'audio_handler') or not self.client.audio_handler:
            return
            
        if not hasattr(self, 'audio_level_bar') or not self.audio_level_bar:
            return
            
        # Get normalized audio level (0.0 to 1.0)
        level = self.client.audio_handler.get_audio_level()
        
        # Convert to bar width (0-50 pixels)
        width = int(level * 50)
        
        # Color based on volume: green (quiet) → yellow (medium) → red (loud)
        if level > 0.7:
            color = "#FF5252"
        elif level > 0.3:
            color = "#FFC107"
        else:
            color = "#4CAF50"
            
        self.audio_level_bar.setFixedWidth(width)
        self.audio_level_bar.setStyleSheet(f"background-color: {color}; border-radius: 2px;")
        
    def handle_audio_status_change(self, is_streaming):
        """
        Handle audio streaming state changes and update UI.
        
        Args:
            is_streaming: True if microphone is active, False otherwise
        """
        if is_streaming:
            self.mute_button.setIcon(QIcon(resource_path("icons/mic_on.png")))
            # Start audio level updates if not running
            if hasattr(self, 'audio_level_timer') and not self.audio_level_timer.isActive():
                self.audio_level_timer.start(100)
        else:
            self.mute_button.setIcon(QIcon(resource_path("icons/mic_off.png")))
            # Stop audio level updates
            if hasattr(self, 'audio_level_timer') and self.audio_level_timer.isActive():
                self.audio_level_timer.stop()
            # Reset level indicator to zero
            if hasattr(self, 'audio_level_bar'):
                self.audio_level_bar.setFixedWidth(0)
                
    def show_message_box(self, title, message, box_type="information"):
        """
        Display styled message box (thread-safe).
        
        Args:
            title: Dialog window title
            message: Message text (supports HTML)
            box_type: Type - "information", "warning", or "critical"
            
        Returns:
            Dialog result code
        """
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        
        # Enable rich text and selection
        msg_box.setTextFormat(Qt.RichText)
        msg_box.setTextInteractionFlags(Qt.TextSelectableByMouse)
        msg_box.setMinimumWidth(400)
        
        # Set icon and color based on type
        if box_type == "information":
            msg_box.setIcon(QMessageBox.Information)
            button_color = "#4CAF50"
        elif box_type == "warning":
            msg_box.setIcon(QMessageBox.Warning)
            button_color = "#ff9800"
        elif box_type == "critical":
            msg_box.setIcon(QMessageBox.Critical)
            button_color = "#d9534f"
        else:
            msg_box.setIcon(QMessageBox.Information)
            button_color = "#4CAF50"
        
        # Apply light theme styling
        self.style_default_message_box(msg_box)
        
        # Custom button color for non-info dialogs
        if button_color != "#4CAF50":
            button_style = f"""
                QMessageBox QPushButton {{
                    background-color: {button_color};
                    color: white;
                    font-weight: bold;
                    padding: 8px 16px;
                    border: none;
                    border-radius: 4px;
                    min-width: 80px;
                }}
                QMessageBox QPushButton:hover {{
                    background-color: {button_color}DD;
                }}
            """
            msg_box.setStyleSheet(msg_box.styleSheet() + button_style)
        
        msg_box.setWindowModality(Qt.WindowModal)
        msg_box.setFocus()
        
        return msg_box.exec_()
    
    def update_screen_share_button(self, can_present, current_presenter):
        """
        Update screen share button state based on active presenter.
        Disables button if another user is presenting.
        
        Args:
            can_present: Whether current user can start presenting
            current_presenter: Username of active presenter (or None)
        """
        if can_present:
            # Enable button - user can present
            self.share_screen_button.setEnabled(True)
            self.share_screen_button.setToolTip("Start screen sharing")
            self.share_screen_button.setStyleSheet(self.screen_share_btn_original_style)
            print("✅ Screen share button ENABLED")
        else:
            # Disable button - another user is presenting
            self.share_screen_button.setEnabled(False)
            self.share_screen_button.setToolTip(
                f"🚫 {current_presenter} is currently presenting.\n"
                f"Wait for them to finish before starting your presentation."
            )
            # Gray out button as visual feedback
            self.share_screen_button.setStyleSheet("""
                QPushButton {
                    background-color: #2a2a2a;
                    color: #666666;
                    border: 1px solid #444444;
                    border-radius: 8px;
                    padding: 10px;
                }
                QPushButton:hover {
                    background-color: #2a2a2a;
                    color: #666666;
                }
                QPushButton:disabled {
                    background-color: #2a2a2a;
                    color: #666666;
                }
            """)
            print(f"🔒 Screen share button DISABLED - {current_presenter} is presenting")