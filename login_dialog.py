"""
Login Dialog Module.
Displays connection dialog for entering server IP and username before joining conference.
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                           QLineEdit, QPushButton, QMessageBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIcon

class LoginDialog(QDialog):
    """Dialog for entering server connection details and username."""
    
    def __init__(self, parent=None):
        """
        Initialize login dialog with input fields and connect button.
        
        Args:
            parent: Parent widget (typically None for initial dialog)
        """
        super().__init__(parent)
        self.setWindowTitle("FusionMeet - Connect to Server")
        self.setFixedSize(450, 220)
        self.setStyleSheet("""
            QDialog {
                background-color: #f0f0f0;
                color: #000000;
            }
            QLabel {
                color: #000000;
            }
        """)
        self.setModal(True)  # Block interaction with other windows
        
        self.layout = QVBoxLayout()
        
        # Application title
        self.title_label = QLabel("FusionMeet")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setFont(QFont("Arial", 18, QFont.Bold))
        self.title_label.setStyleSheet("color: #0066cc; margin: 10px;")
        
        # Server IP input field
        self.ip_layout = QHBoxLayout()
        self.ip_label = QLabel("Server IP:")
        self.ip_label.setFont(QFont("Arial", 12))
        self.ip_label.setMinimumWidth(90)
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("Enter server IP address")
        self.ip_input.setMinimumHeight(40)
        self.ip_input.setFont(QFont("Arial", 12))
        self.ip_input.setStyleSheet("""
            QLineEdit {
                background-color: white;
                color: black;
                padding: 10px;
                border: 2px solid #cccccc;
                border-radius: 5px;
                font-size: 12pt;
            }
        """)
        self.ip_layout.addWidget(self.ip_label)
        self.ip_layout.addWidget(self.ip_input)
        
        # Username input field
        self.username_layout = QHBoxLayout()
        self.username_label = QLabel("Your Name:")
        self.username_label.setFont(QFont("Arial", 12))
        self.username_label.setMinimumWidth(90)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter your name")
        self.username_input.setMinimumHeight(40)
        self.username_input.setFont(QFont("Arial", 12))
        self.username_input.setStyleSheet("""
            QLineEdit {
                background-color: white;
                color: black;
                padding: 10px;
                border: 2px solid #cccccc;
                border-radius: 5px;
                font-size: 12pt;
            }
        """)
        self.username_layout.addWidget(self.username_label)
        self.username_layout.addWidget(self.username_input)
        
        # Connect button with green styling
        self.connect_button = QPushButton("Connect")
        self.connect_button.setMinimumHeight(45)
        self.connect_button.setMinimumWidth(150)
        self.connect_button.setFont(QFont("Arial", 14, QFont.Bold))
        self.connect_button.setCursor(Qt.PointingHandCursor)
        self.connect_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; 
                color: white; 
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self.connect_button.clicked.connect(self.validate_and_accept)
        
        # Assemble dialog layout
        self.layout.addWidget(self.title_label)
        self.layout.addLayout(self.ip_layout)
        self.layout.addLayout(self.username_layout)
        self.layout.addSpacing(10)
        self.layout.addWidget(self.connect_button)
        
        self.setLayout(self.layout)
        
        # Configure tab navigation order
        self.setTabOrder(self.ip_input, self.username_input)
        self.setTabOrder(self.username_input, self.connect_button)
    
    def validate_and_accept(self):
        """
        Validate input fields before accepting dialog.
        Shows error message if server IP or username is empty.
        """
        ip = self.ip_input.text().strip()
        username = self.username_input.text().strip()
        
        # Check if server IP is provided
        # Check if server IP is provided
        if not ip:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Error")
            msg_box.setText("Please enter the server IP address.")
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: white;
                }
                QMessageBox QLabel {
                    color: black;
                    font-size: 13px;
                    min-width: 300px;
                }
                QMessageBox QPushButton {
                    background-color: #ff9800;
                    color: white;
                    padding: 6px 12px;
                    border: none;
                    border-radius: 4px;
                    min-width: 80px;
                }
            """)
            msg_box.exec_()
            return
        
        # Check if username is provided
        # Check if username is provided
        if not username:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Error")
            msg_box.setText("Please enter your name.")
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: white;
                }
                QMessageBox QLabel {
                    color: black;
                    font-size: 13px;
                    min-width: 300px;
                }
                QMessageBox QPushButton {
                    background-color: #ff9800;
                    color: white;
                    padding: 6px 12px;
                    border: none;
                    border-radius: 4px;
                    min-width: 80px;
                }
            """)
            msg_box.exec_()
            return
            
        # Validation passed - accept dialog
        self.accept()
    
    def get_connection_info(self):
        """
        Retrieve connection details after dialog is accepted.
        
        Returns:
            tuple: (server_ip, session_name, username) where session_name is always "Main Session"
        """
        ip = self.ip_input.text().strip()
        username = self.username_input.text().strip()
        
        # Return with default session name
        return ip, "Main Session", username