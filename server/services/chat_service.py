# services/chat_service.py

# Import necessary modules
import asyncio
import json

# Import service modules
from services.db_service import db_service
from services.strands_service import strands_agent, strands_multi_agent
from services.config_service import config_service
from services.websocket_service import send_to_websocket
from services.stream_service import add_stream_task, remove_stream_task

async def handle_chat(data):
    """
    Handle an incoming chat request.

    Workflow:
    - Parse incoming chat data.
    - Optionally inject system prompt.
    - Save chat session and messages to the database.
    - Launch strands_agent task to process chat.
    - Manage stream task lifecycle (add, remove).
    - Notify frontend via WebSocket when stream is done.

    Args:
        data (dict): Chat request data containing:
            - messages: list of message dicts
            - session_id: unique session identifier
            - canvas_id: canvas identifier (contextual use)
            - text_model: text model configuration
            - image_model: image model configuration
    """
    # Extract fields from incoming data
    messages = data.get('messages')
    session_id = data.get('session_id')
    canvas_id = data.get('canvas_id')
    text_model = data.get('text_model')
    image_model = data.get('image_model')
    # TODO: save and fetch system prompt from db or settings config
    system_prompt = data.get('system_prompt')
    auto_model_selection = data.get('auto_model_selection', True)  # 默认开启自动判断

    # If there is only one message, create a new chat session
    if len(messages) == 1:
        # create new session
        prompt = messages[0].get('content', '')
        # TODO: Better way to determin when to create new chat session.
        db_service.create_chat_session(session_id, text_model.get('model'), text_model.get('provider'), canvas_id, (prompt[:200] if isinstance(prompt, str) else ''))

    db_service.create_message(session_id, messages[-1].get('role', 'user'), json.dumps(messages[-1])) if len(messages) > 0 else None

    # Get video model from data (optional)
    video_model = data.get('video_model')

    # Create and start strands agent task for chat processing
    task = asyncio.create_task(strands_agent(
        messages, canvas_id, session_id, text_model, image_model, video_model, system_prompt, auto_model_selection))

    # Register the task in stream_tasks (for possible cancellation)
    add_stream_task(session_id, task)
    try:
        # Await completion of the strands_agent task
        await task
    except asyncio.exceptions.CancelledError:
        print(f"🛑Session {session_id} cancelled during stream")
    finally:
        # Always remove the task from stream_tasks after completion/cancellation
        remove_stream_task(session_id)
        # Notify frontend WebSocket that chat processing is done
        await send_to_websocket(session_id, {
            'type': 'done'
        })
