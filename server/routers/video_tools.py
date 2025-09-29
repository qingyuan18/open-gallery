# server/routers/video_tools.py

# Note: This module is deprecated - video tools should be migrated to Strands format
# from langchain_core.runnables import RunnableConfig
# from langchain_core.tools import tool, InjectedToolCallId
# from typing_extensions import Annotated

# standard libs
import json
import time
import os
import random
import traceback
from io import BytesIO

# third party
import aiofiles
from nanoid import generate

# project utils/services
from utils.http_client import HttpClient
from services.db_service import db_service
from services.websocket_service import send_to_websocket
from common import DEFAULT_PORT

from routers.video_generators import generate_video_replicate

# fastapi exception
from fastapi import HTTPException

def generate_video_file_id():
    return 'vi_' + generate(size=8)

@tool("generate_video", parse_docstring=True)
async def generate_video_tool(
    prompt: str,
    aspect_ratio: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    config: RunnableConfig
):
    """Generate a video using text prompt

    Args:
        prompt: Required. The prompt for video generation. If you want to edit a video, please describe what you want to edit in the prompt.
        aspect_ratio: Required. Aspect ratio of the video, only these values are allowed: 1:1, 16:9, 4:3, 3:4, 9:16 Choose the best fitting aspect ratio according to the prompt. 
    """
    print('🛠️ Video tool_call_id', tool_call_id)
    ctx = config.get('configurable', {})
    canvas_id = ctx.get('canvas_id', '')
    session_id = ctx.get('session_id', '')
    print('🛠️canvas_id', canvas_id, 'session_id', session_id)
    # Inject the tool call id into the context
    ctx['tool_call_id'] = tool_call_id
    args_json = {
        'prompt': prompt,
        'aspect_ratio': aspect_ratio,
    }
    video_model = {
    'model': 'wan-video/wan-2.1-1.3b',
    'provider': 'replicate'
}
    if not video_model:
        raise ValueError("Video model is not selected")
    model = video_model.get('model', '')
    provider = video_model.get('provider', 'replicate')
    try:
        mime_type, width, height, filename = await generate_video_replicate(prompt, model, aspect_ratio)
        file_id = generate_video_file_id()
        url = f'/api/file/{filename}'

        file_data = {
            'mimeType': mime_type,
            'id': file_id,
            'dataURL': url,
            'created': int(time.time() * 1000),
        }

        new_video_element = await generate_new_video_element(canvas_id, file_id, {
            'width': width,
            'height': height,
        })

        # update the canvas data, add the new video element
        canvas_data = db_service.get_canvas_data(canvas_id)
        if 'data' not in canvas_data:
            canvas_data['data'] = {}
        if 'elements' not in canvas_data['data']:
            canvas_data['data']['elements'] = []
        if 'files' not in canvas_data['data']:
            canvas_data['data']['files'] = {}

        canvas_data['data']['elements'].append(new_video_element)
        canvas_data['data']['files'][file_id] = file_data

        print('🛠️canvas_data', canvas_data)

        await db_service.save_canvas_data(canvas_id, json.dumps(canvas_data['data']))

        await send_to_websocket(session_id, {
            'type': 'video_generated',
            'video_data': {
                'element': new_video_element,
                'file': file_data,
            },
        })

        return f"video generated successfully ![video_id: {filename}](http://localhost:{DEFAULT_PORT}/api/file/{filename})"
    except Exception as e:
        print(f"Error generating video: {str(e)}")
        traceback.print_exc()
        await send_to_websocket(session_id, {
            'type': 'error',
            'error': str(e)
        })
        raise HTTPException(status_code=500, detail=str(e))

async def generate_new_video_element(canvas_id: str, fileid: str, video_data: dict):
    canvas = await db_service.get_canvas_data(canvas_id)
    canvas_data = canvas.get('data', {})
    elements = canvas_data.get('elements', [])

    # find the last video element
    last_x = 0
    last_y = 0
    last_width = 0
    last_height = 0
    video_elements = [
        element for element in elements if element.get('type') in ('image','video')]
    last_video_element = video_elements[-1] if len(
        video_elements) > 0 else None
    if last_video_element is not None:
        last_x = last_video_element.get('x', 0)
        last_y = last_video_element.get('y', 0)
        last_width = last_video_element.get('width', 0)
        last_height = last_video_element.get('height', 0)

    new_x = last_x + last_width + 20

    return {
        'type': 'video',
        'id': fileid,
        'x': new_x,
        'y': last_y,
        'width': video_data.get('width', 0),
        'height': video_data.get('height', 0),
        'angle': 0,
        'fileId': fileid,
        'strokeColor': '#000000',
        'fillStyle': 'solid',
        'strokeStyle': 'solid',
        'boundElements': None,
        'roundness': None,
        'frameId': None,
        'backgroundColor': 'transparent',
        'strokeWidth': 1,
        'roughness': 0,
        'opacity': 100,
        'groupIds': [],
        'seed': int(random.random() * 1000000),
        'version': 1,
        'versionNonce': int(random.random() * 1000000),
        'isDeleted': False,
        'index': None,
        'updated': int(time.time() * 1000),
        'link': None,
        'locked': False,
        'status': 'saved',
        'scale': [1, 1],
        'crop': None,
    }
