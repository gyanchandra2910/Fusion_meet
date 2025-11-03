# FusionMeet — Technical Design

This document describes the system architecture, threading model, communication protocols, packet formats, and developer notes for FusionMeet.

## Contents

- System overview
- Component responsibilities
- Communication protocols and ports
- Packet and data formats
- Threading model and concurrency
- Audio mixing (N-1)
- Video and screen frame flow
- File transfer flow
- Packaging/build notes
- Troubleshooting pointers

---

## System overview

FusionMeet uses a client-server architecture optimized for LANs. The server acts as the signalling and media router (and audio mixer) while clients handle capture, encoding, rendering and the GUI.

- Server responsibilities:
  - TCP control channel for authentication, chat, control, and file metadata
  - UDP receiver/sender for media (video/audio/screen)
  - N-1 audio mixing: receives audio from all clients and sends mixed streams back
  - File inventory and transfer coordination

- Client responsibilities:
  - PyQt5 GUI and user interaction
  - Capture audio/video/screen, compress, and send to server
  - Receive remote audio/video frames from server and render
  - Provide file upload/download UI

---

## Communication Protocols & Ports

Default ports (configurable in `config.py`):

- TCP control port: `65435` (control, chat, file metadata, reliable commands)
- UDP media port: `65436` (audio, video, screen frames — low latency)

Protocol choices:

- Use TCP for reliability: login, chat, file metadata and full-file TCP chunk transfer.
- Use UDP for media: lower overhead and latency; code must tolerate packet loss and out-of-order delivery.

---

## Packet formats (high-level)

Note: implementations use `pickle` for structured messages. For cross-language or remote-safe usage consider JSON / protobuf.

- Chat (TCP, pickled dict):

```python
{
  'type': 'chat',
  'username': 'alice',
  'message': 'Hello',
  'timestamp': 1234567890.0
}
```

- Video (UDP, pickled dict):

```python
{
  'type': 'video',
  'username': 'alice',
  'frame': <bytes of JPEG compressed image>,
  'timestamp': 1234567890.0
}
```

- Audio (UDP, raw bytes packed with a small header in some implementations):

```text
[type:'audio'][username(optional)][raw samples]
```

- Video status (TCP):

```python
{'type': 'video_status', 'username': 'alice', 'is_streaming': True}
```

- File metadata and transfer use a size-prefixed protocol via `send_with_size` / `receive_with_size` helpers in `utils.py`.

---

## Threading model

- Server:
  - Main thread: accepts TCP connections
  - One thread per connected client for TCP inbound handling
  - One thread for receiving UDP packets (media)
  - Worker threads for file transfer and long-running tasks

- Client:
  - GUI (main/QApplication) thread: rendering and UI events
  - TCP receiving thread: processes control messages from server
  - UDP receiving thread: receives media packets and dispatches to appropriate handlers
  - Per-module timers/threads: audio loop, video capture timer, screen capture timer

Thread-safety notes:

- GUI updates must happen on the main thread. Use PyQt signals to forward frames/labels from worker threads to the GUI.
- Shared caches (e.g., pending frames while creating a widget) must be protected with `threading.Lock`.

---

## Audio mixing (N-1)

- Server receives raw audio frames from each client.
- For each recipient client X, server mixes all other clients' audio frames (A+B+... excluding X) and sends the mixed frame back to X.
- Use linear PCM mixing with clipping protection. When mixing multiple streams:
  1. Convert to int32 accumulator
  2. Sum samples of all other clients
  3. Divide by number of sources or apply attenuation
  4. Clip back to int16 and send

Notes:
- Mixing adds CPU load on the server; consider using a small thread pool or native optimized code for large participant counts.

---

## Video & Screen flow

- Clients capture frames via OpenCV (video) or MSS (screen), resize to configured resolution (default 320×240), and JPEG-compress to reduce payload.
- Frames are pickled with metadata and sent over UDP to the server.
- Server forwards frames to other participants (it may learn UDP endpoints from incoming packets).
- Clients decode JPEG bytes via `cv2.imdecode` and render via QImage/QPixmap on GUI.

Lossy behavior and robustness:
- Clients drop frames if decode fails or if packet size > UDP limit.
- Use small JPEG quality to fit within single UDP packet (max ~65507 bytes). If you need larger frames, implement fragmentation+reassembly.

---

## File transfer

- File metadata (name, size, session) sent over TCP to server.
- The sender opens a TCP stream to upload file in 32 KB chunks.
- Server stores file in a shared folder and notifies other clients about availability.
- When a client requests a file, server streams file via reliable TCP (size-prefixed or chunked), while clients display progress.

---

## Developer notes & building

- The repo contains two PyInstaller spec files at root:
  - `VideoConference_Client.spec`
  - `VideoConference_Server.spec`

- There is a helper PowerShell script `build_executables.ps1` that activates `.venv` (if exists) and runs PyInstaller for both specs.

Packaging tips:
- Test the packaged app in a clean VM to ensure all dynamic imports are captured (PyQt5 and cv2 often need `--hidden-import`/`--collect-all`).
- If using onefile mode, large resource extraction can take time on startup; consider one-folder build for debugging.

---

## Troubleshooting

- Camera not found: try multiple device indices in `VideoHandler.start_stream()`.
- No audio: check device permissions, and if using Windows, ensure the correct input device index for PyAudio.
- Packet loss / choppy streams: reduce frame rate and/or JPEG quality; prefer wired networks.

---

## Next steps I can help with

1. Produce and commit `docs/ARCHITECTURE.png` (diagram) if you want a PNG (I can generate a mermaid diagram or provide an SVG/PNG tool command).
2. Create CI pipeline (GitHub Actions) to produce executables on push.
3. Add optional TLS (e.g., secure the TCP control channel) and authenticated file sharing.

If you want a runnable executable built now, tell me whether you prefer a one-file build or one-folder build and I'll proceed to run the packaging commands in your environment.
