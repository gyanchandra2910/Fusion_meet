# Build script for FusionMeet (Windows PowerShell)
# Usage: Open PowerShell, cd to repo root and run: .\build_executables.ps1

param(
    [switch]$UseVenv
)

Write-Host "Starting FusionMeet build script..."

# Activate virtual environment if requested or exists
if ($UseVenv -or (Test-Path .\.venv\Scripts\Activate.ps1)) {
    Write-Host "Activating virtual environment .venv"
    & .\.venv\Scripts\Activate.ps1
} else {
    Write-Host "No .venv detected. Make sure your Python environment has required packages installed."
}

# Ensure PyInstaller is installed
$pyinstallerInstalled = (python -c "import pkgutil, sys
if pkgutil.find_loader('PyInstaller'):
    print('yes')
else:
    print('no')")
if ($pyinstallerInstalled -notlike '*yes*') {
    Write-Host "PyInstaller not detected. Installing..."
    pip install pyinstaller
}

# Build client using provided spec if present
if (Test-Path .\VideoConference_Client.spec) {
    Write-Host "Building client with VideoConference_Client.spec"
    pyinstaller .\VideoConference_Client.spec
} else {
    Write-Host "Client spec not found. Building with recommended command..."
    pyinstaller --name="FusionMeet_Client" --icon="client_server_icon/client.ico" --noconsole --onefile client.py
}

# Build server using provided spec if present
if (Test-Path .\VideoConference_Server.spec) {
    Write-Host "Building server with VideoConference_Server.spec"
    pyinstaller .\VideoConference_Server.spec
} else {
    Write-Host "Server spec not found. Building with recommended command..."
    pyinstaller --name="FusionMeet_Server" --icon="client_server_icon/server.ico" --console --onefile server.py
}

Write-Host "Build finished. Check the dist\ directory for outputs."
