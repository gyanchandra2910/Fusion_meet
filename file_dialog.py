"""
FusionMeet File Sharing Dialog
GUI dialog for viewing and downloading shared files within a session.
Displays available files in a table with download functionality.
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                          QTableWidget, QTableWidgetItem, QLabel, QHeaderView,
                          QFileDialog, QMessageBox, QDesktopWidget)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QIcon
from utils import resource_path


class SharedFilesDialog(QDialog):
    """
    Dialog window for managing shared files.
    Allows users to view available files and initiate downloads.
    """
    
    def __init__(self, parent, file_handler):
        """
        Initialize shared files dialog.
        
        Args:
            parent: Parent window
            file_handler: FileSharingHandler instance for file operations
        """
        super().__init__(parent)
        self.setWindowTitle("Shared Files")
        self.setMinimumSize(600, 450)
        self.file_handler = file_handler
        
        # Center dialog on screen
        self.center_on_screen()
        
        # Apply dark theme styling
        self.layout = QVBoxLayout()
        self.setStyleSheet("""
            QDialog {
                background-color: #212121;
                color: white;
            }
            QTableWidget {
                background-color: #333333;
                color: white;
                border: none;
                gridline-color: #444444;
            }
            QTableWidget::item {
                padding: 10px;
            }
            QTableWidget::item:selected {
                background-color: #0078d7;
            }
            QHeaderView::section {
                background-color: #424242;
                color: white;
                padding: 5px;
                border: none;
            }
            QPushButton {
                background-color: #0078d7;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1e88e5;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
            QLabel {
                color: white;
            }
        """)
        
        # Create title label
        self.title_label = QLabel("Available Shared Files")
        self.title_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.title_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.title_label)
        
        # Create files table (3 columns: name, size, action)
        self.files_table = QTableWidget(0, 3)
        self.files_table.setHorizontalHeaderLabels(["File Name", "Size", "Action"])
        self.files_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)  # Filename stretches
        self.files_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Size fits content
        self.files_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Action fits button
        self.files_table.verticalHeader().setVisible(False)  # Hide row numbers
        self.files_table.setSelectionBehavior(QTableWidget.SelectRows)  # Select entire rows
        self.layout.addWidget(self.files_table)
        
        # Create bottom action buttons
        self.buttons_layout = QHBoxLayout()
        
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setIcon(QIcon(resource_path("icons/refresh.png")))
        self.refresh_button.clicked.connect(self.refresh_files)
        
        self.share_button = QPushButton("Share New File")
        self.share_button.setIcon(QIcon(resource_path("icons/file_transfer.png")))
        self.share_button.clicked.connect(self.share_new_file)
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        
        self.buttons_layout.addWidget(self.refresh_button)
        self.buttons_layout.addWidget(self.share_button)
        self.buttons_layout.addWidget(self.close_button)
        
        self.layout.addLayout(self.buttons_layout)
        self.setLayout(self.layout)
        
        # Load initial file list
        self.refresh_files()
    
    def refresh_files(self):
        """
        Update table with latest shared files from server.
        Clears existing entries and repopulates with current file list.
        """
        self.files_table.setRowCount(0)  # Clear all rows
        
        # Populate table with files from file handler
        file_count = 0
        for row, (filename, filesize) in enumerate(self.file_handler.files.items()):
            self.files_table.insertRow(row)
            file_count += 1
            
            # Column 0: File name (read-only)
            name_item = QTableWidgetItem(filename)
            name_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.files_table.setItem(row, 0, name_item)
            
            # Column 1: File size (formatted, centered)
            size_str = self.format_size(filesize)
            size_item = QTableWidgetItem(size_str)
            size_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            size_item.setTextAlignment(Qt.AlignCenter)
            self.files_table.setItem(row, 1, size_item)
            
            # Column 2: Download button
            download_button = QPushButton("Download")
            download_button.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    padding: 5px 10px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            # Connect button to download function with filename
            download_button.clicked.connect(lambda _, f=filename: self.download_file(f))
            
            self.files_table.setCellWidget(row, 2, download_button)
            
        # Show message if no files available
        if file_count == 0:
            self.files_table.setRowCount(1)
            no_files_item = QTableWidgetItem("No files available")
            no_files_item.setFlags(Qt.ItemIsEnabled)  # Not selectable
            no_files_item.setTextAlignment(Qt.AlignCenter)
            self.files_table.setSpan(0, 0, 1, 3)  # Span all 3 columns
            self.files_table.setItem(0, 0, no_files_item)
    
    def format_size(self, size_bytes):
        """
        Convert file size in bytes to human-readable format.
        
        Args:
            size_bytes: File size in bytes
            
        Returns:
            str: Formatted size (e.g., "1.5 MB", "234 KB")
        """
        if size_bytes < 1024:
            return f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
            
    def center_on_screen(self):
        """Position dialog at center of screen."""
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())
    
    def share_new_file(self):
        """
        Open file selection dialog and share selected file with session.
        Refreshes file list after sharing.
        """
        self.file_handler.send_file()
        self.refresh_files()  # Update table with newly shared file
    
    def download_file(self, filename):
        """
        Initiate download for selected file.
        Prompts user for save location and starts transfer.
        
        Args:
            filename: Name of file to download
        """
        # Prevent downloading placeholder message
        if filename == "No files available":
            QMessageBox.information(self, "No Files", "There are no files available for download.")
            return
        
        # Prompt user for save location
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save File As", filename, "All Files (*)"
        )
        
        if save_path:
            # Request download from file handler
            try:
                self.file_handler.request_download(filename)
                QMessageBox.information(
                    self, 
                    "Download Started", 
                    f"Download for {filename} has started.\n\nYou will be notified when it completes.\n\nFile will be saved to:\n{save_path}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self, 
                    "Download Error", 
                    f"Failed to start download: {str(e)}"
                )
