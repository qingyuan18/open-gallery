# services/websocket_state.py
import socketio
from typing import Dict, List

sio = socketio.AsyncServer(
    cors_allowed_origins="*",
    async_mode='asgi'
)

active_connections: Dict[str, dict] = {}

def add_connection(socket_id: str, user_info: dict = None):
    active_connections[socket_id] = user_info or {}
    user_id = user_info.get('id', 'unknown') if user_info else 'unknown'
    print(f"🔌 Client connected: {user_id} (total: {len(active_connections)})")

def remove_connection(socket_id: str):
    if socket_id in active_connections:
        user_info = active_connections[socket_id]
        user_id = user_info.get('id', 'unknown') if user_info else 'unknown'
        del active_connections[socket_id]
        print(f"🔌 Client disconnected: {user_id} (total: {len(active_connections)})")

def get_all_socket_ids():
    return list(active_connections.keys())

def get_user_socket_ids(user_id: str) -> List[str]:
    """Get all socket IDs for a specific user"""
    socket_ids = []
    for socket_id, user_info in active_connections.items():
        if user_info and user_info.get('id') == user_id:
            socket_ids.append(socket_id)
    return socket_ids

def get_connection_count():
    return len(active_connections)

def get_user_connection_count(user_id: str) -> int:
    """Get connection count for a specific user"""
    return len(get_user_socket_ids(user_id))
