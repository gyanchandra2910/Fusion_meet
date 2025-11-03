# 🚀 FusionMeet - LAN-Based All-in-One Collaboration Suite

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PyQt5](https://img.shields.io/badge/PyQt5-GUI-41CD52?style=for-the-badge&logo=qt&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-Video-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

**A powerful, standalone multi-user communication platform designed exclusively for Local Area Networks**

[Features](#-core-features) • [Installation](#-installation--setup) • [Usage](#-usage-instructions) • [Architecture](#-system-architecture) • [Documentation](#-documentation)

</div>

---

## 📖 Overview

**FusionMeet** is a comprehensive LAN-based collaboration suite that brings enterprise-grade communication tools to your local network without requiring internet connectivity. Built entirely in Python using socket programming, it provides real-time video conferencing, crystal-clear audio, screen sharing, instant messaging, and seamless file sharing.

### 🎯 Purpose

Perfect for:
- 🏢 **Corporate environments** with restricted internet access
- 🏫 **Educational institutions** conducting local workshops
- 🏥 **Healthcare facilities** requiring private communication
- 🏭 **Industrial setups** with isolated networks
- 🔒 **Security-conscious organizations** prioritizing data privacy

### ✨ Why FusionMeet?

✅ **100% LAN-Based** - No internet dependency, works entirely offline  
✅ **Complete Privacy** - Your data never leaves your local network  
✅ **Low Latency** - Optimized for real-time communication  
✅ **Easy Deployment** - Simple client-server architecture  
✅ **Feature-Rich** - All essential collaboration tools in one place  
✅ **Open Source** - Fully customizable and transparent  

---

## 🎯 Core Features

### 🎥 Multi-User Video Conferencing
- **Real-time video streaming** from all connected clients
- **Dynamic grid layout** displaying up to 9 participants (3×3)
- **JPEG compression** for efficient bandwidth utilization
- **Configurable quality** - 320×240 resolution at 30 FPS (adjustable in `config.py`)
- **Local preview** with selfie-mode mirroring
- **Thread-safe rendering** using PyQt5 signals/slots

### 🎤 Crystal-Clear Audio Conferencing
- **High-quality audio** - 22050 Hz, 16-bit, mono
- **N-1 Server-side mixing** - Prevents echo by mixing all audio except sender's
- **Real-time transmission** via UDP for minimal latency
- **Visual feedback** - Audio level indicators (planned)
- **Mute/unmute** controls with instant feedback

### 📺 Screen & Presentation Sharing
- **Full screen capture** using MSS library
- **Single presenter mode** - Server-enforced presenter lock
- **Optimized compression** - JPEG at 70% quality, 2 FPS
- **Low-latency delivery** - TCP for reliability
- **Automatic conflict prevention** - Only one presenter at a time
- **FPS counter** for performance monitoring

### 💬 Group Text Chat
- **Real-time messaging** via TCP for guaranteed delivery
- **Persistent chat history** throughout the session
- **Sender identification** - Clear username display
- **Timestamp support** for message tracking
- **Clean UI** - Integrated chat panel in main window

### 📁 File Sharing & Transfer
- **Secure file transfer** over TCP
- **Progress tracking** - Real-time upload/download indicators
- **Transfer speed monitoring** - MB/s display
- **Multi-file support** - Share multiple files simultaneously
- **Centralized storage** - Server manages shared files
- **File listing** - View all available files in session
- **Chunked transfer** - 32 KB chunks for reliable delivery
- **Size limit** - Up to 500 MB per file (configurable)

---

## 🏗️ System Architecture

### Network Topology

```
                    ┌─────────────────┐
                    │  SERVER         │
                    │  (Host Machine) │
                    │                 │
                    │  TCP: 65435     │
                    │  UDP: 65436     │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
         ┌────▼────┐    ┌────▼────┐   ┌────▼────┐
         │ Client1 │    │ Client2 │   │ Client3 │
         │ (Alice) │    │  (Bob)  │   │(Charlie)│
         └─────────┘    └─────────┘   └─────────┘
              │              │              │
              └──────────────┴──────────────┘
                    Same LAN Network
```

### Client-Server Model

**Server Responsibilities:**
- 🔌 Accepts TCP connections on port 65435
- 📡 Routes UDP media packets on port 65436
- 🎵 Performs N-1 audio mixing
- 📂 Manages file inventory and transfers
- 👥 Tracks active participants and sessions
- 🔄 Broadcasts messages and status updates

**Client Responsibilities:**
- 🖥️ PyQt5-based graphical user interface
- 📷 Captures audio, video, and screen content
- 🗜️ Compresses and encodes media streams
- 📤 Sends data to server via TCP/UDP
- 📥 Receives and decodes remote media
- 🎨 Renders video grid and UI components

### Communication Protocols

#### TCP (Port 65435) - Reliable Channel
- ✅ User authentication and login
- ✅ Session management
- ✅ Chat messages
- ✅ File metadata exchange
- ✅ File content transfer
- ✅ Control commands (video/audio status)
- ✅ Participant list updates

#### UDP (Port 65436) - Real-Time Channel
- ⚡ Video frames (JPEG compressed)
- ⚡ Audio chunks (raw PCM)
- ⚡ Screen sharing frames
- ⚡ Low-latency media streams

### Audio Flow Diagram (N-1 Mixing)

```
Client A ───► Server ───► Mix(B+C+D) ───► Client A
Client B ───► Server ───► Mix(A+C+D) ───► Client B
Client C ───► Server ───► Mix(A+B+D) ───► Client C
Client D ───► Server ───► Mix(A+B+C) ───► Client D

Each client receives all audio EXCEPT their own (prevents echo)
```

### Threading Model

**Server Threads:**
1. Main thread - Accepts new TCP connections
2. Per-client TCP handler - One thread per connected client
3. UDP receiver - Single thread for all incoming media
4. Audio mixer - Processes and mixes audio streams

**Client Threads:**
1. Main thread - PyQt5 GUI event loop
2. TCP receiver - Processes control messages from server
3. UDP receiver - Handles incoming media packets
4. Video capture - QTimer-based frame capture (30 FPS)
5. Audio capture - Continuous recording loop
6. Screen capture - QTimer-based capture (2 FPS when active)

---

## 🛠️ Tech Stack & Libraries

### Core Technologies
- **Python 3.8+** - Primary programming language
- **Socket Programming** - TCP/UDP network communication
- **Multi-threading** - Concurrent operations
- **Pickle Protocol** - Data serialization

### Key Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| **PyQt5** | Latest | GUI framework and user interface |
| **OpenCV (cv2)** | Latest | Video capture, processing, and encoding |
| **PyAudio** | Latest | Audio input/output and streaming |
| **NumPy** | Latest | Numerical operations and audio mixing |
| **MSS** | Latest | High-performance screen capture |
| **Pillow (PIL)** | Latest | Image processing and manipulation |

### Development Tools
- **PyInstaller** - Executable packaging
- **Git** - Version control

---

## 📦 Installation & Setup

### System Requirements

**Minimum:**
- OS: Windows 10/11, Linux (Ubuntu 18.04+), macOS 10.14+
- CPU: Intel Core i3 (2.0 GHz) or equivalent
- RAM: 4 GB
- Network: 100 Mbps LAN connection
- Python: 3.8 or higher

**Recommended:**
- CPU: Intel Core i5 (2.5 GHz+) or equivalent
- RAM: 8 GB
- Network: Gigabit (1000 Mbps) Ethernet
- Dedicated GPU for video processing

### Step 1: Clone the Repository

```bash
git clone https://github.com/gyanchandra2910/Fusion_meet.git
cd Fusion_meet
```

### Step 2: Create Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

**Or install manually:**
```bash
pip install PyQt5 opencv-python pyaudio numpy mss pillow
```

### Step 4: Install PyAudio (Windows - if needed)

If PyAudio installation fails on Windows:
```powershell
pip install pipwin
pipwin install pyaudio
```

---

## 🚀 Usage Instructions

### Starting the Server

1. **On the server machine**, navigate to the project directory:

```bash
cd Fusion_meet
```

2. **Activate the virtual environment:**

```powershell
.\.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate      # macOS/Linux
```

3. **Run the server:**

```bash
python server.py
```

4. **Note the server IP address** displayed in the console (e.g., `192.168.1.100`)

**Server Console Output:**
```
╔══════════════════════════════════════════╗
║     FusionMeet Conference Server         ║
╚══════════════════════════════════════════╝
✓ Server started on 192.168.1.100:65435
✓ UDP listening on port 65436
✓ Waiting for clients to connect...
```

### Starting the Client

1. **On each client machine**, navigate to the project directory:

```bash
cd Fusion_meet
```

2. **Activate the virtual environment:**

```powershell
.\.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate      # macOS/Linux
```

3. **Run the client:**

```bash
python client.py
```

4. **Login Dialog:**
   - Enter **Server IP Address** (from Step 4 of server setup)
   - Enter **Your Name** (username)
   - Click **Connect**

5. **Session Join Dialog:**
   - **Create new session** or **select existing session**
   - Click **Join Conference**

### Main Interface Overview

```
┌──────────────────────────────────────────────────────────────┐
│  FusionMeet - Session: Team Meeting                         │
├─────────────────────────┬────────────────────────────────────┤
│                         │  👥 Participants (3)               │
│   VIDEO GRID (3×3)      │  • Alice (You) 🎥 🎤              │
│                         │  • Bob 🎥                          │
│  ┌───────┬───────┬───┐  │  • Charlie 🎥 🎤                   │
│  │ Alice │  Bob  │   │  ├────────────────────────────────────┤
│  │ (You) │       │   │  │  📁 Shared Files (2)               │
│  ├───────┼───────┼───┤  │  📄 Presentation.pdf (2.3 MB)      │
│  │Charlie│       │   │  │     [Download]                     │
│  │       │       │   │  │  📊 Report.xlsx (450 KB)           │
│  ├───────┼───────┼───┤  │     [Download]                     │
│  │       │       │   │  │  [+ Share New File]                │
│  └───────┴───────┴───┘  │                                    │
│                         │                                    │
├─────────────────────────┴────────────────────────────────────┤
│  💬 Chat                                                     │
│  Alice: Welcome to the meeting!                              │
│  Bob: Thanks! Can everyone hear me?                          │
│  Charlie: Yes, loud and clear.                               │
│  [Type your message here...]              [Send]             │
├──────────────────────────────────────────────────────────────┤
│  🎛️ Controls                                                 │
│  [🎥 Video] [🎤 Audio] [📺 Screen] [📁 Files] [🚪 Leave]    │
└──────────────────────────────────────────────────────────────┘
```

### Control Buttons

| Button | Function | Shortcut |
|--------|----------|----------|
| 🎥 **Video** | Toggle camera on/off | - |
| 🎤 **Audio** | Mute/unmute microphone | - |
| 📺 **Screen Share** | Start/stop screen sharing | - |
| 📁 **Files** | Open file sharing dialog | - |
| 💬 **Chat** | Focus chat input | - |
| 🚪 **Leave** | Disconnect from session | - |

### File Sharing Workflow

1. **Upload a file:**
   - Click `📁 Files` or `[+ Share New File]`
   - Select file from file dialog
   - Monitor upload progress
   - File appears in "Shared Files" for all participants

2. **Download a file:**
   - Locate file in "Shared Files" panel
   - Click `[Download]` button
   - Choose save location
   - Monitor download progress

---

## 📂 Folder Structure

```
FusionMeet/
├── 📄 README.md                    # This file
├── 📄 .gitignore                   # Git ignore rules
├── 📄 requirements.txt             # Python dependencies
├── 📄 build_executables.ps1        # Build script for Windows
│
├── 🐍 server.py                    # Main server application
├── 🐍 client.py                    # Main client application
├── 🐍 config.py                    # Configuration constants
├── 🐍 utils.py                     # Network utility functions
│
├── 🎨 gui.py                       # Main GUI window
├── 🎨 login_dialog.py              # Login/connection dialog
├── 🎨 join_media_dialog.py         # Session join dialog
├── 🎨 file_dialog.py               # File sharing dialog
│
├── 🎥 video_module.py              # Video capture and streaming
├── 🎤 audio_module.py              # Audio capture and playback
├── 🎵 audio_mixer.py               # Server-side N-1 audio mixer
├── 📺 screen_sharing_module.py     # Screen capture and sharing
├── 💬 chat_module.py               # Chat messaging
├── 📁 file_sharing_module.py       # File upload/download
│
├── 📦 VideoConference_Client.spec  # PyInstaller spec for client
├── 📦 VideoConference_Server.spec  # PyInstaller spec for server
│
├── 📁 icons/                       # UI icons
│   ├── camera.png
│   ├── mic_on.png
│   ├── mic_off.png
│   ├── video_on.png
│   ├── video_off.png
│   ├── screen_share.png
│   ├── chat.png
│   ├── file_transfer.png
│   └── leave.png
│
├── 📁 client_server_icon/          # Application icons
│   ├── client.ico
│   └── server.ico
│
├── 📁 docs/                        # Documentation
│   └── TECHNICAL.md                # Technical documentation
│
├── 📁 build/                       # Build artifacts (generated)
├── 📁 dist/                        # Executables (generated)
└── 📁 uploads/                     # Shared files storage (generated)
```

---

## 🔧 Building Standalone Executables

### Using the Build Script (Windows)

```powershell
.\build_executables.ps1
```

This will create:
- `dist/FusionMeet_Client.exe`
- `dist/FusionMeet_Server.exe`

### Manual Build (Advanced)

**Build Client:**
```bash
pyinstaller VideoConference_Client.spec
```

**Build Server:**
```bash
pyinstaller VideoConference_Server.spec
```

---

## 🔒 Security Considerations

⚠️ **Important Security Notes:**

- **LAN-Only**: FusionMeet is designed for trusted local networks only
- **No Encryption**: Data is transmitted without encryption by default
- **No Authentication**: Minimal authentication (username only)
- **Trusted Network**: Use only on isolated, trusted LANs
- **Firewall**: Ensure proper firewall rules on the server machine

**DO NOT expose the server to the public internet without implementing:**
- TLS/SSL encryption for TCP
- DTLS for UDP (or VPN)
- Strong authentication (passwords, tokens)
- Authorization and access control

---

## 🐛 Troubleshooting

### Common Issues

**1. "Cannot connect to server"**
- ✅ Verify server IP address
- ✅ Check firewall settings (allow ports 65435, 65436)
- ✅ Ensure both machines are on the same LAN
- ✅ Ping server: `ping <server_ip>`

**2. "No video/black screen"**
- ✅ Check camera permissions
- ✅ Ensure camera is not used by another app
- ✅ Try toggling video off and on
- ✅ Restart client application

**3. "No audio from other participants"**
- ✅ Check microphone permissions
- ✅ Toggle microphone mute/unmute
- ✅ Verify correct audio device selected
- ✅ Use headphones to prevent echo

**4. "Choppy video/audio"**
- ✅ Reduce video resolution in `config.py`
- ✅ Use wired Ethernet instead of WiFi
- ✅ Check network bandwidth
- ✅ Close bandwidth-intensive applications

**5. "Screen sharing not working"**
- ✅ Check screen recording permissions (macOS)
- ✅ Only one presenter allowed at a time
- ✅ Restart screen sharing if black screen appears

### Performance Optimization

**Server-Side:**
- Use a dedicated machine for the server
- Ensure sufficient CPU for audio mixing (multi-core recommended)
- Monitor network bandwidth usage

**Client-Side:**
- Reduce video quality if experiencing lag
- Use wired connection for better stability
- Close unnecessary applications

---

## 📊 Performance Metrics

**Bandwidth Requirements (per client):**
- Audio: ~86 Kbps (22050 Hz × 16-bit × 1 channel)
- Video: ~400-800 Kbps (320×240, JPEG compressed)
- Screen Share: ~1-2 Mbps (when active)
- **Total**: ~2-3 Mbps per active client

**Example: 10 Clients**
- Server bandwidth: ~30 Mbps
- Recommended LAN: Gigabit (1000 Mbps)

---

## 🚧 Future Improvements

### Planned Features
- [ ] **End-to-end encryption** for all communications
- [ ] **User authentication** with password protection
- [ ] **Session recording** (audio/video)
- [ ] **Virtual backgrounds** for video
- [ ] **Noise suppression** for audio
- [ ] **Breakout rooms** for smaller discussions
- [ ] **Whiteboard** for collaborative drawing
- [ ] **Polls and reactions** for engagement
- [ ] **Admin controls** for session management
- [ ] **Mobile client** (Android/iOS)

### Technical Enhancements
- [ ] **Adaptive bitrate** for varying network conditions
- [ ] **WebRTC integration** for peer-to-peer mode
- [ ] **Database backend** for persistent sessions
- [ ] **REST API** for external integrations
- [ ] **Docker containers** for easy deployment
- [ ] **Load balancing** for multiple servers
- [ ] **Metrics dashboard** for monitoring

---

## 👥 Contributors

<div align="center">

### Lead Developer
**Gyan Chandra**  
[GitHub](https://github.com/gyanchandra2910)

</div>

### How to Contribute

We welcome contributions! Here's how you can help:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/AmazingFeature`)
3. **Commit** your changes (`git commit -m 'Add some AmazingFeature'`)
4. **Push** to the branch (`git push origin feature/AmazingFeature`)
5. **Open** a Pull Request

**Contribution Guidelines:**
- Follow PEP 8 style guide for Python code
- Add comments and docstrings to your code
- Test your changes thoroughly
- Update documentation as needed

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

```
MIT License

Copyright (c) 2025 Gyan Chandra

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
```

---

## 🙏 Acknowledgments

Special thanks to the open-source community and the following projects:

- **PyQt5** - Riverbank Computing for the excellent GUI framework
- **OpenCV** - Intel for computer vision capabilities
- **PyAudio** - Hubert Pham for audio I/O
- **NumPy** - NumPy developers for numerical operations
- **MSS** - BoboTiG for screen capture functionality
- **Python Software Foundation** - For the amazing Python language

---

## 📞 Support & Contact

**Issues & Bug Reports:**  
[GitHub Issues](https://github.com/gyanchandra2910/Fusion_meet/issues)

**Documentation:**  
[Technical Documentation](docs/TECHNICAL.md)

**Questions?**  
Feel free to open a discussion or contact the maintainer.

---

<div align="center">

### 🌟 Star this repository if you find it useful!

**Made with ❤️ for seamless LAN collaboration**

[⬆ Back to Top](#-fusionmeet---lan-based-all-in-one-collaboration-suite)

</div>
