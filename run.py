#!/usr/bin/env python3
"""
FusionMeet Application Launcher.
Handles virtual environment setup, dependency installation, and application startup.
Provides menu for launching server, client, or both.
"""

import os
import sys
import subprocess
import platform
import pkg_resources

# Required packages for FusionMeet to function
REQUIRED_PACKAGES = [
    'PyQt5',
    'opencv-python',
    'numpy',
    'pyaudio',
    'mss',
    'pillow',
    'pipwin',  # Helps Windows users install PyAudio
]

def check_venv():
    """
    Check if script is running inside a virtual environment.
    
    Returns:
        bool: True if in virtual environment, False otherwise
    """
    return hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)

def create_venv():
    """Create a new virtual environment in 'venv' directory."""
    print("Creating virtual environment...")
    subprocess.check_call([sys.executable, '-m', 'venv', 'venv'])
    print("Virtual environment created.")

def activate_venv():
    """
    Activate virtual environment and restart script within it.
    Determines correct activation path based on OS.
    """
    if platform.system() == 'Windows':
        activate_script = os.path.join('venv', 'Scripts', 'activate.bat')
        python = os.path.join('venv', 'Scripts', 'python.exe')
    else:
        activate_script = os.path.join('venv', 'bin', 'activate')
        python = os.path.join('venv', 'bin', 'python')
    
    # Restart script in virtual environment
    os.execl(python, python, *sys.argv)

def get_missing_packages():
    """
    Check which required packages are not installed.
    
    Returns:
        list: Names of missing packages
    """
    missing = []
    for package in REQUIRED_PACKAGES:
        try:
            pkg_resources.get_distribution(package)
        except pkg_resources.DistributionNotFound:
            missing.append(package)
    return missing

def install_packages(packages):
    """
    Install specified packages using pip.
    
    Args:
        packages: List of package names to install
    """
    print(f"Installing required packages: {', '.join(packages)}")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + packages)
    print("All required packages installed.")

def get_local_ip():
    """
    Get local machine's IP address by connecting to external server.
    
    Returns:
        str: Local IP address or '127.0.0.1' if unable to determine
    """
    import socket
    try:
        # Connect to Google DNS to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return '127.0.0.1'  # Fallback to localhost

def display_menu():
    """
    Display interactive menu and get user's choice.
    
    Returns:
        str: User's menu choice ('1', '2', '3', or '4')
    """
    print("\n" + "="*50)
    print("FusionMeet - Choose an option:")
    print("="*50)
    print("1. Start the server")
    print("2. Start a client")
    print("3. Start both server and client (single-user mode)")
    print("4. Exit")
    print("="*50)
    
    while True:
        choice = input("Enter your choice (1-4): ")
        if choice in ['1', '2', '3', '4']:
            return choice
        print("Invalid choice. Please enter 1, 2, 3, or 4.")

def main():
    """
    Main launcher function.
    Ensures virtual environment and dependencies, then shows menu for starting server/client.
    """
    print("Starting FusionMeet...")
    
    # Ensure running in virtual environment
    if not check_venv():
        print("Virtual environment not detected.")
        create_venv()
        activate_venv()
        return  # Script will restart in venv
    
    # Install any missing dependencies
    missing_packages = get_missing_packages()
    if missing_packages:
        install_packages(missing_packages)
    
    # Main menu loop
    while True:
        choice = display_menu()
        
        if choice == '1':
            # Start server only
            print("\nStarting FusionMeet Server...")
            local_ip = get_local_ip()
            print(f"Server will be available at: {local_ip}")
            print(f"Other users can connect to this address: {local_ip}")
            print("\nPress Ctrl+C to stop the server.")
            try:
                subprocess.call([sys.executable, 'server.py'])
            except KeyboardInterrupt:
                print("\nServer stopped.")
            
        elif choice == '2':
            # Start client only
            print("\nStarting FusionMeet Client...")
            subprocess.call([sys.executable, 'client.py'])
            
        elif choice == '3':
            # Start both server and client for single-user testing
            print("\nStarting FusionMeet in single-user mode (server + client)...")
            local_ip = get_local_ip()
            print(f"Server started at: {local_ip}")
            print(f"Other users can connect to this address: {local_ip}")
            
            # Launch server in background
            server_process = subprocess.Popen([sys.executable, 'server.py'])
            
            # Wait for server initialization
            import time
            time.sleep(1)
            
            # Start client (blocks until closed)
            print("Starting client...")
            subprocess.call([sys.executable, 'client.py'])
            
            # Terminate server when client exits
            server_process.terminate()
            print("Server stopped.")
            
        elif choice == '4':
            # Exit application
            print("\nThank you for using FusionMeet!")
            break

if __name__ == "__main__":
    main()