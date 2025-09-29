import os
import time
from fastapi import APIRouter, HTTPException, status
import requests
from services.config_service import config_service
from services.db_service import db_service

#services
from services.files_service import download_file
from services.websocket_service import broadcast_init_done

router = APIRouter(prefix="/api")

# @router.get("/workspace_list")
# async def workspace_list():
#     return [{"name": entry.name, "is_dir": entry.is_dir(), "path": str(entry)} for entry in Path(WORKSPACE_ROOT).iterdir()]

async def initialize():
    # await initialize_mcp()
    await broadcast_init_done()

@router.get("/workspace_download")
async def workspace_download(path: str):
    return download_file(path)

def get_ollama_model_list():
    # Check if Ollama is configured with API key or models
    ollama_config = config_service.get_config().get('ollama', {})

    # Skip Ollama if no models are configured and no API key is set
    if not ollama_config.get('models') and not ollama_config.get('api_key'):
        return []

    base_url = ollama_config.get('url', os.getenv('OLLAMA_HOST', 'http://localhost:11434'))
    try:
        response = requests.get(f'{base_url}/api/tags', timeout=5)
        response.raise_for_status()
        data = response.json()
        return [model['name'] for model in data.get('models', [])]
    except requests.RequestException as e:
        # Only print error if Ollama is explicitly configured
        if ollama_config.get('models') or ollama_config.get('api_key'):
            print(f"Error querying Ollama: {e}")
        return []


@router.get("/list_models")
async def get_models():
    config = config_service.get_config()
    res = []
    ollama_models = get_ollama_model_list()
    ollama_url = config_service.get_config().get('ollama', {}).get(
        'url', os.getenv('OLLAMA_HOST', 'http://localhost:11434'))

    # Only print ollama_models if there are any or if Ollama is configured
    ollama_config = config_service.get_config().get('ollama', {})
    if ollama_models or ollama_config.get('models') or ollama_config.get('api_key'):
        print('👇ollama_models', ollama_models)
    for ollama_model in ollama_models:
        res.append({
            'provider': 'ollama',
            'model': ollama_model,
            'url': ollama_url,
            'type': 'text'
        })
    for provider in config.keys():
        models = config[provider].get('models', {})
        for model_name in models:
            if provider == 'ollama':
                continue
            # Skip providers that require API key but don't have one (except bedrock and comfyui)
            if provider not in ['comfyui', 'bedrock'] and config[provider].get('api_key', '') == '':
                continue
            model = models[model_name]
            res.append({
                'provider': provider,
                'model': model_name,
                'url': config[provider].get('url', ''),
                'type': model.get('type', 'text'),
                'media_type': model.get('media_type')
            })
    return res


@router.get("/list_chat_sessions")
async def list_chat_sessions():
    """List all chat sessions for the authenticated user"""
    try:
        return db_service.list_all_user_sessions()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list chat sessions: {str(e)}"
        )


@router.get("/chat_session/{session_id}")
async def get_chat_session(session_id: str):
    """Get chat history and last image info for the authenticated user"""
    try:
        messages = db_service.get_chat_history(session_id)
        print(f"🔍 DEBUG: API returning {len(messages)} messages for session {session_id}")
        print(f"🔍 DEBUG: Messages content: {messages}")

        # 获取最后一幅图像
        last_image_id = ""
        try:
            from tools.strands_image_generators import get_most_recent_image_from_session
            from services.user_context import get_current_user_id
            user_id = get_current_user_id()
            last_image_id = get_most_recent_image_from_session(session_id, user_id)
        except Exception as e:
            print(f"❌ Error getting last image for session {session_id}: {e}")

        result = {
            "messages": messages,
            "last_image_id": last_image_id
        }
        print(f"🔍 DEBUG: Final API response: {result}")
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get chat session: {str(e)}"
        )

@router.post("/chat_session/{session_id}/message")
async def save_message(session_id: str, request: dict):
    """Save a single message to the chat session for the authenticated user"""
    try:
        role = request.get('role', 'assistant')
        content = request.get('content', '')

        print(f"🔍 DEBUG: Saving message to session {session_id}")
        print(f"🔍 DEBUG: Role: {role}")
        print(f"🔍 DEBUG: Content type: {type(content)}")
        print(f"🔍 DEBUG: Content: {content}")

        # Convert content to string if it's not already
        if isinstance(content, dict) or isinstance(content, list):
            import json
            content = json.dumps(content)
            print(f"🔍 DEBUG: Converted content to JSON string: {content}")

        db_service.create_message(session_id, role, content)
        print(f"✅ DEBUG: Message saved successfully to database")

        return {"success": True, "message": "Message saved successfully"}
    except ValueError as e:
        print(f"❌ DEBUG: ValueError saving message: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        print(f"❌ Error saving message: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save message"
        )

@router.get("/chat_session/{session_id}/status")
async def get_chat_session_status(session_id: str):
    """Get session status including messages and processing state for the authenticated user"""
    try:
        from services.stream_service import get_stream_task

        messages = db_service.get_chat_history(session_id)
        task = get_stream_task(session_id)
        is_processing = task is not None and not task.done()

        return {
            "session_id": session_id,
            "messages": messages,
            "is_processing": is_processing,
            "timestamp": int(time.time() * 1000)  # 毫秒时间戳
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get chat session status: {str(e)}"
        )
