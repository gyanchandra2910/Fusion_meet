"""
Join Call Dialog Module.
Displays dialog for selecting camera and microphone settings before joining conference.
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QCheckBox, QPushButton, QGroupBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

class JoinMediaDialog(QDialog):
    """Dialog allowing user to enable/disable camera and microphone before joining call."""
    
    def __init__(self, parent=None):
        """
        Initialize join call dialog with default media settings enabled.
        
        Args:
            parent: Parent widget (typically MainWindow)
        """
        super().__init__(parent)
        self.setWindowTitle("Join Call - FusionMeet")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        # Default both camera and mic to enabled
        self.camera_enabled = True
        self.mic_enabled = True
        
        self.setup_ui()
        
    def setup_ui(self):
        """Create dialog UI with media checkboxes and action buttons."""
        layout = QVBoxLayout()
        layout.setSpacing(20)
        
        # Dialog title
        header = QLabel("Join Call")
        header.setFont(QFont("Arial", 16, QFont.Bold))
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)
        
        # Instructions text
        desc = QLabel("Choose your audio and video settings:")
        desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc)
        
        # Media settings section
        media_group = QGroupBox("Media Settings")
        media_layout = QVBoxLayout()
        
        # Camera toggle checkbox (default: enabled)
        self.camera_checkbox = QCheckBox("Enable Camera")
        self.camera_checkbox.setChecked(True)
        self.camera_checkbox.setFont(QFont("Arial", 10))
        media_layout.addWidget(self.camera_checkbox)
        
        # Microphone toggle checkbox (default: enabled)
        self.mic_checkbox = QCheckBox("Enable Microphone")
        self.mic_checkbox.setChecked(True)
        self.mic_checkbox.setFont(QFont("Arial", 10))
        media_layout.addWidget(self.mic_checkbox)
        
        media_group.setLayout(media_layout)
        layout.addWidget(media_group)
        
        # Action buttons (Cancel and Join)
        button_layout = QHBoxLayout()
        
        # Cancel button - closes dialog without joining
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setMinimumWidth(100)
        
        # Join button - confirms selection and proceeds to join call
        self.join_button = QPushButton("Join Call")
        self.join_button.clicked.connect(self.accept)
        self.join_button.setMinimumWidth(100)
        self.join_button.setDefault(True)  # Enter key triggers this button
        
        # Style buttons with light theme colors
        self.join_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.join_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        layout.addStretch()
        
        self.setLayout(layout)
        
        # Light theme dialog styling for better readability
        self.setStyleSheet("""
    QDialog {
        background-color: #ffffff;
        color: #000000;
    }

    QLabel {
        color: #000000;
        background-color: transparent;
    }

    QGroupBox {
        background-color: #f9f9f9;
        color: #000000;
        border: 1px solid #ccc;
        border-radius: 8px;
        margin-top: 10px;
    }

    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px;
        background-color: transparent;
    }

    QCheckBox {
        color: #000000;
        background-color: transparent;
    }

    QPushButton {
        background-color: #f0f0f0;
        color: #000000;
        border-radius: 4px;
        padding: 8px;
    }

    QPushButton:hover {
        background-color: #e0e0e0;
    }
""")

    
    def get_selections(self):
        """
        Get user's camera and microphone preferences from checkboxes.
        
        Returns:
            tuple: (camera_enabled, mic_enabled) as boolean values
        """
        self.camera_enabled = self.camera_checkbox.isChecked()
        self.mic_enabled = self.mic_checkbox.isChecked()
        return self.camera_enabled, self.mic_enabled
