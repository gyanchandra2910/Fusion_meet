"""
FusionMeet Utility Functions
Helper functions for network communication and resource management.
"""

import struct
import sys
import os


def resource_path(relative_path):
    """
    Get absolute path to resource, works for both development and PyInstaller builds.
    
    Args:
        relative_path: Relative path to resource file (e.g., 'icons/mute.png')
        
    Returns:
        str: Absolute path to resource
    """
    try:
        # PyInstaller: use temporary extraction folder
        base_path = sys._MEIPASS
    except Exception:
        # Development: use current directory
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)


def receive_exact(sock, num_bytes):
    """
    Receive exact number of bytes from socket.
    Handles partial receives until complete.
    
    Args:
        sock: Socket to receive from
        num_bytes: Exact number of bytes to receive
        
    Returns:
        bytes: Received data, or None if connection closed
    """
    data = b''
    while len(data) < num_bytes:
        # Request remaining bytes
        packet = sock.recv(num_bytes - len(data))
        if not packet:
            # Connection closed
            return None
        data += packet
    return data


def send_with_size(sock, data):
    """
    Send data prefixed with 4-byte size header.
    Format: [4-byte size][data]
    
    Args:
        sock: Socket to send to
        data: Data to send (bytes)
    """
    # Pack size as 4-byte unsigned int (network byte order)
    size = struct.pack('!I', len(data))
    sock.sendall(size + data)


def receive_with_size(sock):
    """
    Receive data prefixed with 4-byte size header.
    Complements send_with_size.
    
    Args:
        sock: Socket to receive from
        
    Returns:
        bytes: Received data, or None if connection closed
    """
    # Read 4-byte size header
    size_data = receive_exact(sock, 4)
    if not size_data:
        return None
    
    # Unpack size and read exact payload
    size = struct.unpack('!I', size_data)[0]
    return receive_exact(sock, size)
