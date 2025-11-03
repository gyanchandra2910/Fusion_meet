"""
FusionMeet Audio Mixer
Server-side audio mixing using N-1 approach to prevent echo
"""

import numpy as np
import time
import threading

class AudioMixer:
    """
    Server-side audio mixer implementing N-1 mixing strategy.
    Each client receives audio from all participants except themselves to prevent echo.
    """
    
    def __init__(self, channels=1, sample_rate=22050, chunk_size=2048):
        """
        Initialize audio mixer with specified parameters.
        
        Args:
            channels: Number of audio channels (1=mono, 2=stereo)
            sample_rate: Audio sample rate in Hz
            chunk_size: Number of samples per audio chunk
        """
        self.channels = channels
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.frame_size = chunk_size * channels * 2  # 2 bytes per sample (16-bit)
        
        # Store latest audio frame from each user {username: audio_bytes}
        self.audio_buffers = {}
        self.audio_buffer_lock = threading.Lock()
        
        # Pre-generate silent audio chunk for efficiency
        AUDIO_DTYPE = np.int16
        self.SILENT_CHUNK_NP = np.zeros(chunk_size, dtype=AUDIO_DTYPE)
        self.SILENT_CHUNK_BYTES = self.SILENT_CHUNK_NP.tobytes()
        
        # Calculate expected audio payload size
        BYTES_PER_SAMPLE = 2  # 16-bit audio
        self.EXPECTED_PAYLOAD_SIZE = chunk_size * BYTES_PER_SAMPLE
        
        # Statistics tracking
        self.mix_count = 0
        self.last_mix_time = time.time()
    
    def add_frame(self, username, frame_data, audio_level=None):
        """
        Store new audio frame from a user.
        
        Args:
            username: Identifier of the user sending audio
            frame_data: Raw audio bytes (PCM 16-bit)
            audio_level: Optional audio level (not currently used)
            
        Returns:
            bool: True if frame added successfully, False otherwise
        """
        # Validate input
        if not frame_data or not isinstance(frame_data, bytes):
            return False
        
        # Store frame in buffer (thread-safe)
        with self.audio_buffer_lock:
            self.audio_buffers[username] = frame_data
        
        return True
    
    def get_mixed_frame_n_minus_1(self, exclude_username):
        """
        Mix audio from all users except the specified one (N-1 mixing).
        This prevents users from hearing their own audio, eliminating echo.
        
        Args:
            exclude_username: Username to exclude from the mix
            
        Returns:
            bytes: Mixed audio data as PCM 16-bit bytes, or silence if no audio available
        """
        with self.audio_buffer_lock:
            # Get all speakers except the excluded user
            speakers = [u for u in self.audio_buffers.keys() if u != exclude_username]
            
            # Return silence if no other speakers
            if not speakers:
                return self.SILENT_CHUNK_BYTES
            
            # Collect audio from each speaker
            audio_arrays = []
            for speaker in speakers:
                try:
                    audio_data = self.audio_buffers[speaker]
                    
                    # Ensure audio data is correct size (pad or truncate)
                    if len(audio_data) != self.EXPECTED_PAYLOAD_SIZE:
                        if len(audio_data) < self.EXPECTED_PAYLOAD_SIZE:
                            # Pad with zeros
                            audio_data = audio_data + b'\x00' * (self.EXPECTED_PAYLOAD_SIZE - len(audio_data))
                        else:
                            # Truncate excess
                            audio_data = audio_data[:self.EXPECTED_PAYLOAD_SIZE]
                    
                    # Convert bytes to numpy array for mixing
                    audio_np = np.frombuffer(audio_data, dtype=np.int16)
                    audio_arrays.append(audio_np)
                    
                except Exception:
                    # Skip invalid audio data
                    continue
            
            # Return silence if no valid audio collected
            if not audio_arrays:
                return self.SILENT_CHUNK_BYTES
            
            # Mix audio streams
            try:
                # Use int32 to prevent overflow during summing
                mixed = np.zeros(self.chunk_size, dtype=np.int32)
                for audio_array in audio_arrays:
                    mixed += audio_array.astype(np.int32)
                
                # Average the audio to prevent clipping
                num_speakers = len(audio_arrays)
                if num_speakers > 1:
                    mixed = (mixed / num_speakers).astype(np.int32)
                
                # Clip to valid int16 range and convert
                mixed = np.clip(mixed, -32768, 32767).astype(np.int16)
                
                # Convert back to bytes
                return mixed.tobytes()
                
            except Exception:
                # Return silence on mixing error
                return self.SILENT_CHUNK_BYTES
    
    def get_mixed_frame(self, exclude_username=None):
        """
        Mix all audio frames into a single output.
        Wrapper for backward compatibility - uses N-1 mixing if username provided.
        
        Args:
            exclude_username: Optional username to exclude from mix
            
        Returns:
            bytes: Mixed audio data
        """
        # Use N-1 mixing if exclusion specified
        if exclude_username:
            return self.get_mixed_frame_n_minus_1(exclude_username)
        
        # Mix all participants together
        with self.audio_buffer_lock:
            speakers = list(self.audio_buffers.keys())
            
            if not speakers:
                return self.SILENT_CHUNK_BYTES
            
            # Collect audio data
            audio_arrays = []
            for speaker in speakers:
                try:
                    audio_data = self.audio_buffers[speaker]
                    
                    # Validate and normalize size
                    if len(audio_data) != self.EXPECTED_PAYLOAD_SIZE:
                        if len(audio_data) < self.EXPECTED_PAYLOAD_SIZE:
                            audio_data = audio_data + b'\x00' * (self.EXPECTED_PAYLOAD_SIZE - len(audio_data))
                        else:
                            audio_data = audio_data[:self.EXPECTED_PAYLOAD_SIZE]
                    
                    audio_np = np.frombuffer(audio_data, dtype=np.int16)
                    audio_arrays.append(audio_np)
                    
                except Exception:
                    continue
            
            if not audio_arrays:
                return self.SILENT_CHUNK_BYTES
            
            # Mix audio
            try:
                mixed = np.zeros(self.chunk_size, dtype=np.int32)
                for audio_array in audio_arrays:
                    mixed += audio_array.astype(np.int32)
                
                # Average to prevent clipping
                if len(audio_arrays) > 1:
                    mixed = (mixed / len(audio_arrays)).astype(np.int32)
                
                # Clip and convert
                mixed = np.clip(mixed, -32768, 32767).astype(np.int16)
                return mixed.tobytes()
                
            except Exception as e:
                print(f"Error mixing audio: {e}")
                return self.SILENT_CHUNK_BYTES
    
    def clear_buffer(self, username):
        """
        Remove audio buffer for a specific user.
        Called when user disconnects or stops transmitting.
        
        Args:
            username: User whose buffer should be removed
        """
        with self.audio_buffer_lock:
            if username in self.audio_buffers:
                del self.audio_buffers[username]
    
    def clear_all_buffers(self):
        """
        Clear all stored audio buffers.
        Useful for session reset or cleanup.
        """
        with self.audio_buffer_lock:
            self.audio_buffers.clear()
    
    def get_active_speakers(self):
        """
        Get list of users currently transmitting audio.
        
        Returns:
            list: Usernames of active speakers
        """
        with self.audio_buffer_lock:
            return list(self.audio_buffers.keys())
    
    def get_stats(self):
        """
        Get mixer statistics for monitoring and debugging.
        
        Returns:
            dict: Statistics including frame count, active speakers, etc.
        """
        with self.audio_buffer_lock:
            return {
                'total_frames_processed': self.mix_count,
                'active_speakers': len(self.audio_buffers),
                'frame_size': self.frame_size,
                'chunk_size': self.chunk_size,
                'channels': self.channels
            }
