# routers/websocket_router.py
from services.websocket_state import sio, add_connection, remove_connection
from middleware.auth_middleware import WebSocketAuthenticationMiddleware

@sio.event
async def connect(sid, environ, auth):
    # Authenticate WebSocket connection
    user_info = WebSocketAuthenticationMiddleware.authenticate_websocket_connection(auth or {})

    if user_info:
        add_connection(sid, user_info)
        print(f"🔌 WebSocket connected: {user_info.get('username', user_info.get('id', 'Unknown'))}")
        await sio.emit('connected', {'status': 'connected', 'user': user_info}, room=sid)
    else:
        print(f"❌ WebSocket authentication failed for {sid}")
        await sio.emit('auth_error', {'error': 'Authentication failed'}, room=sid)
        await sio.disconnect(sid)

@sio.event
async def disconnect(sid):
    print(f"Client {sid} disconnected")
    remove_connection(sid)

@sio.event
async def ping(sid, data):
    await sio.emit('pong', data, room=sid)
