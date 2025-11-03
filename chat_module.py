"""
FusionMeet Chat Module
Real-time text messaging between conference participants.
Uses TCP for reliable message delivery.
"""

import pickle
from datetime import datetime


class ChatHandler:
    """
    Handles sending and receiving chat messages.
    Integrates with GUI to display messages in chat panel.
    """
    
    def __init__(self, client):
        """
        Initialize chat handler.
        
        Args:
            client: Reference to main client instance
        """
        self.client = client
        self.username = "User"  # Will be set from client.username

    def send_message(self, text):
        """
        Send chat message to all participants in session.
        
        Args:
            text: Message content to send
        """
        # Get current username from client or use default
        username = self.client.username if hasattr(self.client, 'username') else self.username
        
        # Create message packet with metadata
        message = {
            'type': 'chat',
            'sender': username,
            'timestamp': datetime.now().strftime('%H:%M:%S'),  # Format: HH:MM:SS
            'text': text
        }
        
        # Serialize and send via TCP for guaranteed delivery
        data = pickle.dumps(message)
        self.client.send_tcp(data)

    def handle_message(self, data):
        """
        Process incoming chat message and display in GUI.
        
        Args:
            data: Pickled message data from server
        """
        try:
            # Deserialize message packet
            message = pickle.loads(data)
            
            # Verify it's a chat message
            if message['type'] == 'chat':
                # Display message in chat panel if GUI is available
                if self.client.gui:
                    self.client.gui.add_chat_message(message['sender'], message['text'])
                    
        except (pickle.UnpicklingError, KeyError):
            # Ignore corrupted or non-chat messages
            pass
