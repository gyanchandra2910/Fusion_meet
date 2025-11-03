"""
FusionMeet Configuration
Central configuration file for server and client settings.
Contains network ports, media parameters, and GUI styling.
"""

# =============================================================================
# NETWORK CONFIGURATION
# =============================================================================

# Server network settings
HOST = '0.0.0.0'  # Bind to all network interfaces (allows external connections)
TCP_PORT = 65435  # Control channel port (chat, signaling, file transfers)
UDP_PORT = 65436  # Media channel port (audio, video streams)

# Client default server address
SERVER_HOST = '127.0.0.1'  # Default localhost (overridden by login dialog)


# =============================================================================
# VIDEO STREAM CONFIGURATION
# =============================================================================

VIDEO_WIDTH = 640   # Frame width in pixels
VIDEO_HEIGHT = 480  # Frame height in pixels
VIDEO_FPS = 20      # Target frames per second (balance between quality and bandwidth)


# =============================================================================
# AUDIO STREAM CONFIGURATION
# =============================================================================

# Core audio parameters
AUDIO_FORMAT = 8       # PyAudio format: paInt16 (16-bit PCM audio)
AUDIO_CHANNELS = 1     # Mono audio (reduces bandwidth, prevents phase issues)
AUDIO_RATE = 22050     # Sample rate in Hz (balance between quality and bandwidth)
AUDIO_CHUNK = 2048     # Samples per buffer (larger = more latency, smaller = more CPU)

# Audio buffering and processing
AUDIO_BUFFER_MS = 60   # Output buffer size in milliseconds (prevents crackling)
AUDIO_MIN_LEVEL = 0.005  # Silence detection threshold (0.0 = silent, 1.0 = max volume)
AUDIO_FALLBACK_RATES = [48000, 16000, 8000]  # Alternative rates if hardware doesn't support default
AUDIO_MAX_RETRY = 3    # Retry attempts for audio device initialization
AUDIO_DEVICE_TIMEOUT = 2.0  # Seconds to wait when testing audio devices

# Audio quality enhancement
AUDIO_DYNAMIC_GAIN = True   # Automatically adjust volume levels
AUDIO_NORMALIZE = True      # Normalize audio to prevent clipping
AUDIO_FRAME_TIMEOUT = 0.2   # Seconds before discarding stale audio frames


# =============================================================================
# FILE SHARING CONFIGURATION
# =============================================================================

FILE_CHUNK_SIZE = 32768  # 32 KB per chunk (balance between memory and transfer speed)
DEFAULT_DOWNLOAD_DIR = "G_meet_downloads"  # Download folder name (created in user's Downloads)
MAX_FILE_SIZE = 1024 * 1024 * 500  # 500 MB maximum file size (prevents memory issues)


# =============================================================================
# GUI STYLING
# =============================================================================

# Color scheme (dark theme)
APP_BG_COLOR = "#212121"     # Main background color (dark gray)
BUTTON_BG_COLOR = "#333333"  # Button background (lighter gray)
TEXT_COLOR = "#FFFFFF"       # Text color (white)
ACCENT_COLOR = "#00BFFF"     # Accent color for highlights (blue)
