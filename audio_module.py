"""
FusionMeet Audio Module
Handles microphone capture, audio transmission, and playback
"""

import pyaudio
import pickle
import struct
import threading
import time
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, Qt

from config import *

class AudioHandler(QObject):
    """
    Client-side audio capture and playback handler.
    Manages microphone input and speaker output for voice conferencing.
    """
    
    # PyQt signal for UI audio status updates
    audio_status_changed = pyqtSignal(bool)
    
    # Audio configuration constants
    AUDIO_FORMAT = pyaudio.paInt16  # 16-bit PCM audio
    CHANNELS = 1                     # Mono audio
    RATE = 22050                     # Sample rate (Hz)
    CHUNK = 2048                     # Samples per buffer
    
    def __init__(self, client):
        """
        Initialize audio handler.
        
        Args:
            client: Reference to main client instance for network communication
        """
        super().__init__()
        self.client = client
        
        # Audio state flags
        self.is_streaming = False  # Microphone capture active
        self.is_receiving = True   # Speaker playback always ready
        
        # PyAudio streams
        self.p = pyaudio.PyAudio()
        self.input_stream = None   # Microphone input
        self.output_stream = None  # Speaker output
        
        # Audio level monitoring for UI
        self.audio_level = 0
        self.audio_level_update_time = time.time()
        
        # Rate limiting for audio transmission
        self.last_send_time = 0
        self.min_send_interval = 0.02  # 20ms between packets
        
        # Statistics tracking
        self.audio_sent_count = 0
        self.audio_received_count = 0
        self.last_stats_time = time.time()
        
        # Background thread for audio capture
        self.audio_send_thread = None
        
        # Initialize speaker output immediately (always ready to receive)
        self.start_receiving()
        print("🔊 Audio output stream started (ready to hear others)")
        
    def start_receiving(self):
        """
        Start audio receiving (speaker output).
        Initializes speaker stream to play incoming audio from other clients.
        
        Returns:
            bool: True if successfully started, False otherwise
        """
        if self.is_receiving and self.output_stream:
            print("⚠️ Output stream already running, skipping...")
            return True
            
        try:
            print("🔊 Starting audio output stream...")
            
            # Clean up any existing stream
            if self.output_stream:
                try:
                    self.output_stream.stop_stream()
                    self.output_stream.close()
                except:
                    pass
                self.output_stream = None
            
            # Create speaker output stream with minimal latency settings
            self.output_stream = self.p.open(
                format=self.AUDIO_FORMAT, 
                channels=self.CHANNELS, 
                rate=self.RATE,
                output=True, 
                frames_per_buffer=self.CHUNK,
                stream_callback=None,
                output_device_index=None,
                start=False  # Start manually to avoid initial buffer buildup
            )
            
            # Start stream after creation to prevent latency
            self.output_stream.start_stream()
            
            self.is_receiving = True
            print("✅ Audio output stream ready - you can now hear others!")
            print(f"📊 Stream info: Rate={self.RATE}, Channels={self.CHANNELS}, Chunk={self.CHUNK}")
            return True
            
        except Exception as e:
            print(f"❌ Error starting audio output stream: {e}")
            import traceback
            traceback.print_exc()
            if self.output_stream:
                try:
                    self.output_stream.close()
                except:
                    pass
                self.output_stream = None
            self.is_receiving = False
            return False

    def stop_receiving(self):
        """
        Stop audio receiving (speaker output).
        
        Returns:
            bool: True if successfully stopped, False if already stopped
        """
        if not self.is_receiving:
            return False
            
        print("🔊 Stopping audio output stream...")
        self.is_receiving = False
        
        if self.output_stream:
            try:
                self.output_stream.stop_stream()
                self.output_stream.close()
            except Exception as e:
                print(f"Error closing output stream: {e}")
            self.output_stream = None
        
        print("🔇 Audio output stream stopped")
        return True

    def start_stream(self):
        """
        Start audio sending (microphone capture).
        Initializes microphone input and begins background thread for audio transmission.
        
        Returns:
            bool: True if successfully started, False if already streaming
        """
        if self.is_streaming:
            return False
            
        try:
            print("🎤 Starting audio input (microphone)...")
            
            # Clean up any existing input stream
            if self.input_stream:
                try:
                    self.input_stream.stop_stream()
                    self.input_stream.close()
                except:
                    pass
                self.input_stream = None
            
            # Create microphone input stream
            self.input_stream = self.p.open(
                format=self.AUDIO_FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK
            )
            
            # Mark as streaming and notify UI
            self.is_streaming = True
            self.audio_status_changed.emit(True)
            
            # Start background thread for audio capture and transmission
            self.audio_send_thread = threading.Thread(target=self._audio_send_loop, daemon=True)
            self.audio_send_thread.start()
            
            print("✅ Microphone started - others can now hear you!")
            return True
            
        except Exception as e:
            print(f"❌ Error starting audio input: {e}")
            if hasattr(e, 'errno') and e.errno == -9996:
                print("Hint: No input device found. Is a microphone connected?")
            
            # Clean up on error
            if self.input_stream:
                try:
                    self.input_stream.close()
                except:
                    pass
                self.input_stream = None
            
            self.is_streaming = False
            return False

    def stop_stream(self):
        """
        Stop audio sending (microphone capture).
        Stops capture thread and clears audio buffers to prevent noise artifacts.
        
        Returns:
            bool: True if successfully stopped, False if already stopped
        """
        if not self.is_streaming:
            return False
            
        print("🎤 Stopping microphone...")
        self.is_streaming = False
        
        # Wait for send thread to finish
        if self.audio_send_thread and self.audio_send_thread.is_alive():
            self.audio_send_thread.join(timeout=1.0)
        
        # Close input stream
        if self.input_stream:
            try:
                self.input_stream.stop_stream()
                self.input_stream.close()
            except Exception as e:
                print(f"Error closing input stream: {e}")
            self.input_stream = None
        
        # Clear output buffer to prevent noise artifacts when microphone stops
        if self.output_stream:
            try:
                silence = b'\x00' * (self.CHUNK * 2)
                for _ in range(3):  # Write silence frames to flush buffer
                    try:
                        self.output_stream.write(silence, exception_on_underflow=False)
                    except:
                        break
                print("🔇 Output buffer cleared to prevent noise")
            except Exception as e:
                print(f"Note: Could not clear buffer: {e}")
        
        # Notify UI of status change
        self.audio_status_changed.emit(False)
        
        print("🔇 Microphone stopped.")
        return True

    def _audio_send_loop(self):
        """
        Background thread: continuously captures and transmits microphone audio.
        Reads audio from microphone and sends via UDP while streaming is active.
        """
        print("🎤 Audio send loop started")
        
        while self.is_streaming:
            if not self.is_streaming or not self.input_stream:
                time.sleep(0.01)
                continue
                continue
            try:
                # Read audio data from microphone
                data = self.input_stream.read(self.CHUNK, exception_on_overflow=False)
                
                # Prepend audio packet type header
                payload = b'a|' + data
                
                # Create and send audio packet to server
                audio_packet = {
                    'type': 'audio',
                    'username': self.client.username,
                    'raw_data': payload
                }
                pickled = pickle.dumps(audio_packet)
                self.client.send_udp(pickled)
                
                self.audio_sent_count += 1
                
                # Debug logging every 50 packets
                if self.audio_sent_count % 50 == 0:
                    print(f"📤 Sent {self.audio_sent_count} audio packets to server")
                
            except IOError as e:
                # Buffer overflow can happen, usually recoverable
                if self.is_streaming:
                    print(f"Audio read warning (overflow?): {e}")
            except Exception as e:
                if self.is_streaming:
                    print(f"Error in _audio_send_loop: {e}")
                    self.stop_stream()
                    time.sleep(1)
        
        print("🎤 Audio send loop ended")
    
    def handle_audio(self, data):
        """
        Handle incoming audio data from other clients.
        Receives mixed audio from server and plays through speakers.
        
        Args:
            data: Pickled audio packet containing mixed audio frame
        """
        # Ensure output stream is available
        if not self.output_stream or not self.is_receiving:
            print("⚠️ No output stream available! Trying to start...")
            if not self.start_receiving():
                print("❌ Failed to start output stream")
                return
            
        try:
            # Unpack incoming audio packet
            payload = pickle.loads(data)
            
            # Extract audio frame (server sends mixed audio in 'frame' field)
            if 'frame' in payload:
                audio_frame = payload.get('frame')
                
                if audio_frame and len(audio_frame) > 0:
                    try:
                        # Buffer management to prevent excessive delay
                        # Drop packets only if buffer is critically full
                        if self.output_stream:
                            try:
                                available = self.output_stream.get_write_available()
                                
                                # Drop packet if less than half a chunk of space available
                                if available < self.CHUNK*0.5:
                                    self.audio_received_count += 1
                                    if self.audio_received_count % 200 == 0:
                                        print(f"⚠️ Buffer full - dropping packets")
                                    return  # Skip packet to prevent delay buildup
                            except:
                                pass  # Continue if buffer check fails
                        
                        # Ensure stream is active before writing
                        if not self.output_stream.is_active():
                            print("⚠️ Output stream not active! Starting it...")
                            self.output_stream.start_stream()
                        
                        # Play audio through speakers
                        if self.output_stream:
                            self.output_stream.write(audio_frame, exception_on_underflow=False)
                            self.audio_received_count += 1
                            
                            # Debug logging
                            if self.audio_received_count % 100 == 0:
                                print(f"🔊 Received {self.audio_received_count} audio packets | Wrote {len(audio_frame)} bytes")
                    except IOError as e:
                        if self.is_receiving:
                            print(f"❌ Audio output IOError: {e}")
                            # Try to restart stream on error
                            try:
                                self.stop_receiving()
                                time.sleep(0.1)
                                self.start_receiving()
                            except:
                                pass
                    except Exception as e:
                        if self.is_receiving and self.audio_received_count % 100 == 0:
                            print(f"❌ Unexpected audio write error: {e}")
                return
            
            # Handle alternative raw_data format (legacy compatibility)
            if 'raw_data' in payload:
                raw_data = payload['raw_data']
                
                # Parse packet format: "type|data" (e.g., b'a|audio_bytes')
                try:
                    parts = raw_data.split(b'|', 1)
                    if len(parts) >= 2 and parts[0] == b'a':
                        media_data = parts[1]
                        
                        # Same buffer management as above
                        if self.output_stream:
                            try:
                                available = self.output_stream.get_write_available()
                                if available < self.CHUNK:
                                    self.audio_received_count += 1
                                    return  # Drop if critically full
                            except:
                                pass
                        
                        # Ensure stream is active
                        if not self.output_stream.is_active():
                            print("⚠️ Output stream not active! Starting it...")
                            self.output_stream.start_stream()
                        
                        # Write audio to output stream
                        if self.output_stream:
                            try:
                                self.output_stream.write(media_data, exception_on_underflow=False)
                                self.audio_received_count += 1
                                
                                if self.audio_received_count % 100 == 0:
                                    print(f"🔊 Received {self.audio_received_count} audio packets (raw_data) | Wrote {len(media_data)} bytes")
                            except OSError as e:
                                if self.is_receiving:
                                    print(f"❌ Audio output OSError: {e}")
                            except Exception as e:
                                if self.is_receiving:
                                    print(f"❌ Unexpected audio write error: {e}")
                except Exception as e:
                    print(f"❌ Error parsing raw audio format: {e}")
                        
        except pickle.UnpicklingError:
            pass  # Silently ignore corrupted packets
        except Exception as e:
            if self.is_receiving and self.audio_received_count % 100 == 0:
                print(f"❌ Error in handle_audio: {e}")

    def get_audio_level(self):
        """
        Get current microphone audio input level.
        
        Returns:
            float: Audio level from 0.0 (silent) to 1.0 (loud)
        """
        return self.audio_level

    def get_audio_stats(self):
        """
        Get audio statistics for debugging and monitoring.
        
        Returns:
            dict: Statistics including packet counts and stream states
        """
        return {
            'sent_count': self.audio_sent_count,
            'received_count': self.audio_received_count,
            'is_streaming': self.is_streaming,
            'is_receiving': self.is_receiving,
            'audio_level': self.audio_level
        }
        
    def __del__(self):
        """Cleanup audio resources when object is destroyed."""
        try:
            self.stop_stream()
            self.stop_receiving()
            if hasattr(self, 'p') and self.p:
                self.p.terminate()
        except Exception as e:
            print(f"Error during audio handler cleanup: {e}")