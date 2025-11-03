# 🎯 FusionMeet - LAN-Based Video Conferencing System# G-Meet Clone



<div align="center">This project is a LAN-based multi-user communication system developed in Python, mimicking some of the core functionalities of Google Meet. It uses a client-server architecture and socket programming to enable real-time video/audio conferencing, screen sharing, group chat, and file sharing among multiple users on the same local network.



![FusionMeet](https://img.shields.io/badge/FusionMeet-LAN%20Conferencing-blue?style=for-the-badge)## Features

[![Python](https://img.shields.io/badge/Python-3.8+-green?style=for-the-badge&logo=python)](https://www.python.org/)

[![PyQt5](https://img.shields.io/badge/PyQt5-GUI-orange?style=for-the-badge)](https://riverbankcomputing.com/software/pyqt/)- **Multi-User Video Conferencing**: Real-time video streaming from all clients, displayed in a dynamic grid.

- **Multi-User Audio Conferencing**: Real-time audio streaming and playback.

**A robust, standalone communication platform for Local Area Networks**- **Screen Sharing**: A designated "presenter" can share their screen with all other participants.

- **Group Text Chat**: A chronological group chat for all participants.

[Features](#-features) • [Installation](#-installation) • [Quick Start](#-quick-start) • [Architecture](#-system-architecture) • [Documentation](#-documentation)- **File Sharing**: Share files with all participants in the session. Files are listed in the shared files panel, making it easy for any participant to download them.

- **Integrated File Panel**: View and download shared files directly in the main interface.

</div>- **Modular Design**: Each major functionality (video, audio, chat, etc.) is handled in a separate module for clarity and extensibility.



---## Architecture



## 📋 Table of ContentsThe system is built on a client-server model:



- [Overview](#-overview)- **Server (`server.py`)**: A central, multi-threaded server that manages all client connections and routes data between them. It uses separate threads for handling each client's TCP connection and a main thread for UDP traffic.

- [Features](#-features)- **Client (`client.py`)**: A GUI application (built with PyQt5) that provides the user interface for all functionalities. It uses multiple threads to handle sending and receiving data for different modules concurrently.

- [System Requirements](#-system-requirements)

- [Installation](#-installation)### Communication Protocols

- [Quick Start](#-quick-start)

- [User Guide](#-user-guide)- **TCP**: Used for reliable, ordered data transfer, which is essential for:

- [System Architecture](#-system-architecture)  - Session management (connections, disconnections)

- [Technical Specifications](#-technical-specifications)  - Group chat messages

- [Building Executables](#-building-executables)  - File sharing (both metadata and file content)

- [Troubleshooting](#-troubleshooting)    - File metadata is sent to all clients when a new file is shared

- [License](#-license)    - File content is sent in chunks only when a specific client requests it

    - The server tracks available files for each session and sends this information to new clients

---  - Screen sharing frames (for reliability over speed)

- **UDP**: Used for low-latency, real-time data, where speed is more critical than perfect reliability:

## 🌟 Overview  - Video streams

  - Audio streams

**FusionMeet** is a comprehensive, server-based multi-user communication application designed to operate exclusively over Local Area Networks (LAN). Perfect for environments where internet access is unavailable, unreliable, or restricted, FusionMeet provides enterprise-grade collaboration tools without requiring external connectivity.

### Threading Model

### Why FusionMeet?

Both the client and server are heavily multi-threaded to ensure non-blocking operations:

✅ **100% LAN-Based** - No internet required  

✅ **Complete Privacy** - Data never leaves your network  - **Server**:

✅ **Low Latency** - Optimized for real-time communication    - Main thread: Listens for new TCP connections.

✅ **Easy Setup** - Simple server-client architecture    - One thread per connected client to handle all incoming TCP data from that client.

✅ **All-in-One** - Video, audio, chat, screen sharing, and file transfer    - One thread to listen for all incoming UDP data.

- **Client**:

---  - Main thread: Runs the PyQt5 GUI application.

  - One thread for receiving all TCP data from the server.

## 🚀 Features  - One thread for receiving all UDP data from the server.

  - Separate `QTimer` or thread-based mechanisms within each module (e.g., video, audio) for sending data at regular intervals.

### 🎥 Multi-User Video Conferencing

- **Real-time Video Streaming** - UDP protocol for low-latency transmission## Modules

- **JPEG Compression** - Efficient bandwidth utilization

- **Grid Layout** - Display multiple participants simultaneously- `config.py`: Contains all the configuration variables for the server and client.

- **Configurable Quality** - 320x240 @ 15 FPS (adjustable)- `utils.py`: Provides helper functions for network communication, such as sending and receiving data with size prefixes.

- `gui.py`: Defines the main window and all the UI components for the client application.

### 🎤 Multi-User Audio Conferencing- `chat_module.py`: Handles the logic for sending and receiving chat messages.

- **Crystal Clear Audio** - 22050 Hz, mono, 16-bit- `video_module.py`: Manages video capturing, encoding, sending, receiving, and decoding.

- **N-1 Audio Mixing** - Server-side mixing prevents echo- `audio_module.py`: Manages audio recording, encoding, sending, receiving, and playback.

- **Real-time Transmission** - UDP for minimal latency- `screen_sharing_module.py`: Handles screen capturing and transmission.

- **Audio Level Indicators** - Visual feedback- `file_sharing_module.py`: Implements the file sending and receiving logic, with support for:

.\.venv\Scripts\Activate.ps1

# Run client
python client.py
```

1. Enter server IP address
2. Choose username
3. Select/create session
4. Click "Join Conference"

---

## 📖 User Guide

### Main Interface
```
┌─────────────────────────────────────────────────────┐
│  FusionMeet - Session: Team Meeting                │
├───────────┬────────────────────┬────────────────────┤
│  Video    │  Screen Share      │  Participants      │
│  Grid     │  (when active)     │  • Alice (You)     │
│           │                    │  • Bob             │
│  ┌──┬──┐  │                    ├────────────────────┤
│  │A │B │  │                    │  Shared Files      │
│  ├──┼──┤  │                    │  📄 Report.pdf     │
│  │C │D │  │                    │  📊 Slides.pptx    │
│  └──┴──┘  │                    │                    │
├───────────┴────────────────────┼────────────────────┤
│  Chat                          │  Controls          │
│  Alice: Hello!                 │  🎥 🎤 📺 📁 🚪   │
│  [Type message...]    [Send]   │                    │
└────────────────────────────────┴────────────────────┘
```

### Controls

**🎥 Video:** Toggle camera on/off  
**🎤 Audio:** Toggle microphone mute  
**📺 Screen Share:** Start/stop presenting  
**📁 Files:** Upload/download files  
**💬 Chat:** Send text messages  
**🚪 Leave:** Disconnect from session  

---

## 🏗️ System Architecture

### Network Topology
```
                ┌─────────────┐
                │   Server    │
                │ (192.168.x) │
                └──────┬──────┘
                       │
       ┌───────────────┼───────────────┐
       │               │               │
  ┌────▼────┐     ┌────▼────┐    ┌────▼────┐
  │ Client1 │     │ Client2 │    │ Client3 │
  │ (Alice) │     │  (Bob)  │    │(Charlie)│
  └─────────┘     └─────────┘    └─────────┘
```

### Communication Protocols

**TCP (Port 5000):**
- User authentication
- Chat messages
- File transfers
- Control commands

**UDP (Port 5001):**
- Audio streams
- Video streams
- Screen sharing
- Real-time data

### Audio Flow (N-1 Mixing)
```
Client A ──► Server ──► Mix(B+C) ──► Client A
Client B ──► Server ──► Mix(A+C) ──► Client B  
Client C ──► Server ──► Mix(A+B) ──► Client C

Each client receives all others except themselves
```

---

## 🔧 Technical Specifications

### Network Packets

**Audio Packet (UDP):**
```
[Type:'a'] [Audio Data: 4096 bytes]
```

**Video Packet (UDP):**
```
[Type:'v'] [Username Length] [Username] [JPEG Data]
```

**Chat Message (TCP):**
```json
{
    "type": "chat",
    "username": "Alice",
    "message": "Hello!",
    "timestamp": 1699000000
}
```

### Configuration

**Audio:**
- Sample Rate: 22050 Hz
- Channels: Mono (1)
- Bit Depth: 16-bit
- Chunk: 2048 samples

**Video:**
- Resolution: 320x240
- Frame Rate: 15 FPS
- Compression: JPEG (~50%)
- Protocol: UDP

**File Transfer:**
- Chunk Size: 32 KB
- Protocol: TCP
- Max Size: 500 MB

---

## 🛠️ Building Executables

### Build Client
```powershell
pyinstaller --name="FusionMeet_Client" \
    --icon="client_server_icon/client.ico" \
    --noconsole \
    --onefile \
    --add-data="icons;icons" \
    --add-data="config.py;." \
    --add-data="utils.py;." \
    --add-data="audio_module.py;." \
    --add-data="audio_mixer.py;." \
    --add-data="video_module.py;." \
    --add-data="screen_sharing_module.py;." \
    --add-data="chat_module.py;." \
    --add-data="file_sharing_module.py;." \
    --add-data="gui.py;." \
    --add-data="login_dialog.py;." \
    --add-data="join_media_dialog.py;." \
    --add-data="file_dialog.py;." \
    --hidden-import=PyQt5 \
    --hidden-import=pyaudio \
    --hidden-import=cv2 \
    --hidden-import=numpy \
    --hidden-import=PIL \
    --hidden-import=mss \
    --collect-all=PyQt5 \
    --collect-all=cv2 \
    --collect-all=numpy \
    --collect-all=PIL \
    --collect-all=mss \
    --collect-all=pyaudio \
    client.py
```

### Build Server
```powershell
pyinstaller --name="FusionMeet_Server" \
    --icon="client_server_icon/server.ico" \
    --console \
    --onefile \
    --add-data="config.py;." \
    --add-data="utils.py;." \
    --add-data="audio_mixer.py;." \
    --hidden-import=numpy \
    --collect-all=numpy \
    server.py
```

**Output:** `dist/FusionMeet_Client.exe` and `dist/FusionMeet_Server.exe`

---

## 🐛 Troubleshooting

### Audio Issues

**No audio from others:**
- Check microphone permissions
- Toggle mic off/on
- Verify audio device in settings
- Use headphones to prevent echo

**Echo/feedback:**
- Use headphones instead of speakers
- N-1 mixing should prevent this
- Check for duplicate connections

### Video Issues

**Black screen:**
- Check camera permissions
- Ensure camera not used by other app
- Toggle camera off/on
- Restart client

**Choppy video:**
- Reduce resolution in `config.py`
- Check network bandwidth
- Use wired connection

### Network Issues

**Cannot connect:**
- Verify server IP address
- Check firewall settings
- Ensure same LAN network
- Ping server: `ping <server_ip>`

**Connection drops:**
- Check network stability
- Use ethernet instead of WiFi
- Verify no network congestion

### Screen Share Issues

**"Another user presenting":**
- Wait for current presenter
- Only one presenter at a time

**Black screen share:**
- Check screen capture permissions
- Restart sharing
- Restart client

---

## 🔐 Security

**Network Security:**
- ⚠️ LAN-only, do NOT expose to internet
- No encryption by default
- Trust-based system
- Use on trusted networks only

**Firewall Setup (Windows):**
```powershell
New-NetFirewallRule -DisplayName "FusionMeet TCP" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow
New-NetFirewallRule -DisplayName "FusionMeet UDP" -Direction Inbound -Protocol UDP -LocalPort 5001 -Action Allow
```

---

## 📊 Performance

**Bandwidth (per client):**
- Audio: ~86 Kbps
- Video: ~400-800 Kbps
- Screen Share: ~1-2 Mbps
- **Total:** ~2-3 Mbps per client

**For 10 clients:** ~30 Mbps server bandwidth required

**Recommended:** Gigabit LAN (1000 Mbps)

---

## 📝 Project Structure

```
FusionMeet/
├── server.py                  # Main server
├── client.py                  # Main client
├── config.py                  # Configuration
├── utils.py                   # Utilities
├── audio_module.py            # Audio handler
├── audio_mixer.py             # N-1 mixing
├── video_module.py            # Video handler
├── screen_sharing_module.py   # Screen share
├── chat_module.py             # Chat handler
├── file_sharing_module.py     # File transfer
├── gui.py                     # Main window
├── login_dialog.py            # Login UI
├── join_media_dialog.py       # Join UI
├── file_dialog.py             # File UI
├── icons/                     # GUI icons
└── client_server_icon/        # App icons
```

---

## 📄 License

MIT License - See LICENSE file for details

---

## 🙏 Acknowledgments

- PyQt5 - GUI framework
- OpenCV - Video processing
- PyAudio - Audio I/O
- NumPy - Numerical ops
- MSS - Screen capture
- Pillow - Image processing

---

<div align="center">

**Made with ❤️ for LAN Collaboration**

[⬆ Back to Top](#-fusionmeet---lan-based-video-conferencing-system)

</div>
