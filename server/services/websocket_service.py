# services/websocket_service.py
from services.websocket_state import sio, get_all_socket_ids, get_user_socket_ids
import traceback

async def broadcast_session_update(session_id: str, canvas_id: str, event: dict, user_id: str = None):
    """Broadcast session update to specific user or all users"""
    if user_id:
        # Send to specific user only
        socket_ids = get_user_socket_ids(user_id)
    else:
        # Legacy behavior - send to all (for backward compatibility)
        socket_ids = get_all_socket_ids()

    if socket_ids:
        try:
            for socket_id in socket_ids:
                await sio.emit('session_update', {
                    'canvas_id': canvas_id,
                    'session_id': session_id,
                    **event
                }, room=socket_id)
        except Exception as e:
            print(f"Error broadcasting session update for {session_id}: {e}")
            traceback.print_exc()

async def send_to_user_websocket(session_id: str, event: dict, user_id: str):
    """Send WebSocket message to a specific user"""
    await broadcast_session_update(session_id, None, event, user_id)

# compatible with legacy codes
# TODO: All Broadcast should have a canvas_id and user_id
async def send_to_websocket(session_id: str, event: dict):
    await broadcast_session_update(session_id, None, event)

async def broadcast_init_done():
    try:
        await sio.emit('init_done', {
            'type': 'init_done'
        })
        print("🚀 System initialized")
    except Exception as e:
        print(f"Error broadcasting init_done: {e}")
        traceback.print_exc()
