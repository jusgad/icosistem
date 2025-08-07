"""
WebSocket events and handlers.
"""

from flask_socketio import SocketIO
from flask import current_app
import logging

logger = logging.getLogger(__name__)

def register_socketio_events(socketio: SocketIO):
    """
    Registrar todos los eventos de WebSocket.
    
    Args:
        socketio: Instancia de SocketIO
    """
    
    @socketio.on('connect')
    def handle_connect():
        """Manejar nueva conexión WebSocket."""
        logger.info('Client connected to WebSocket')
        
    @socketio.on('disconnect')
    def handle_disconnect():
        """Manejar desconexión WebSocket."""
        logger.info('Client disconnected from WebSocket')
        
    @socketio.on('ping')
    def handle_ping():
        """Responder a ping para mantener conexión."""
        return 'pong'
    
    logger.info("WebSocket events registered successfully")