from fastapi.responses import FileResponse
from common import DEFAULT_PORT
from tools.strands_image_generators import generate_file_id
from services.db_service import db_service
import traceback
from services.config_service import USER_DATA_DIR, FILES_DIR
from services.websocket_service import send_to_websocket, broadcast_session_update

from PIL import Image
from io import BytesIO
import os
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form, status
import httpx
import aiofiles
from mimetypes import guess_type
from utils.http_client import HttpClient

router = APIRouter(prefix="/api")
os.makedirs(FILES_DIR, exist_ok=True)

# 上传图片接口，支持表单提交
@router.post("/upload_image")
async def upload_image(file: UploadFile = File(...)):
    """Upload image for the authenticated user"""
    try:
        print('🦄upload_image file', file.filename)
        # 生成文件 ID 和文件名
        file_id = generate_file_id()
        filename = file.filename or ''

        # Read the file content
        content = await file.read()

        # Open the image from bytes to get its dimensions
        with Image.open(BytesIO(content)) as img:
            width, height = img.size

        # Determine the file extension
        mime_type, _ = guess_type(filename)
        # default to 'bin' if unknown
        extension = mime_type.split('/')[-1] if mime_type else 'bin'

        # 保存图片到本地
        full_file_id = f'{file_id}.{extension}'
        file_path = os.path.join(FILES_DIR, full_file_id)
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)

        # 创建文件记录到数据库
        try:
            db_service.create_file(full_file_id, full_file_id, width, height)
        except Exception as e:
            print(f"❌ Error creating file record: {e}")
            # Continue even if database record creation fails

        # 返回文件信息
        print('🦄upload_image file_path', file_path)
        return {
            'file_id': full_file_id,
            'url': f'/api/file/{full_file_id}',
            'width': width,
            'height': height,
        }
    except Exception as e:
        print(f"❌ Error uploading image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload image: {str(e)}"
        )


# 文件下载接口
@router.get("/file/{file_id}")
async def get_file(file_id: str):
    """Get file with user verification when possible"""
    # 首先尝试从数据库获取文件信息并验证用户权限
    try:
        from services.user_context import get_current_user_id
        user_id = get_current_user_id()
        file_record = db_service.get_file(file_id)
        if file_record:
            # 数据库中有记录，使用数据库中的文件路径
            file_path = os.path.join(FILES_DIR, file_record['file_path'])
            print(f'🦄get_file from database (user verified): {file_path}')
            if os.path.exists(file_path):
                return FileResponse(file_path)
    except Exception as e:
        print(f'🦄get_file database/auth error: {e}')
        # Continue with fallback for backward compatibility

    # 向后兼容：如果数据库中没有记录或用户验证失败，尝试直接查找文件
    # 这是为了支持旧的文件，但新文件应该都有用户验证
    # 首先尝试原始文件名
    file_path = os.path.join(FILES_DIR, file_id)
    print(f'🦄get_file trying direct path (fallback): {file_path}')
    if os.path.exists(file_path):
        return FileResponse(file_path)

    # 如果没有扩展名，尝试常见的图像扩展名
    if '.' not in file_id:
        for ext in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
            file_path_with_ext = os.path.join(FILES_DIR, f'{file_id}.{ext}')
            print(f'🦄get_file trying with extension (fallback): {file_path_with_ext}')
            if os.path.exists(file_path_with_ext):
                return FileResponse(file_path_with_ext)

    print(f'🦄get_file not found: {file_id}')
    raise HTTPException(status_code=404, detail="File not found")


@router.post("/comfyui/object_info")
async def get_object_info(data: dict):
    url = data.get('url', '')
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    try:
        timeout = httpx.Timeout(10.0)
        async with HttpClient.create(timeout=timeout) as client:
            response = await client.get(f"{url}/api/object_info")
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(
                    status_code=response.status_code, detail=f"ComfyUI server returned status {response.status_code}")
    except Exception as e:
        if "ConnectError" in str(type(e)) or "timeout" in str(e).lower():
            print(f"ComfyUI connection error: {str(e)}")
            raise HTTPException(
                status_code=503, detail="ComfyUI server is not available. Please make sure ComfyUI is running.")
        print(f"Unexpected error connecting to ComfyUI: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to connect to ComfyUI: {str(e)}")
