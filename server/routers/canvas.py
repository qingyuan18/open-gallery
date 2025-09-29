from fastapi import APIRouter, Request, HTTPException, status
#from routers.agent import chat
from services.chat_service import handle_chat
from services.db_service import db_service
import asyncio
import json

router = APIRouter(prefix="/api/canvas")

@router.get("/list")
async def list_canvases():
    """Get all canvases for the authenticated user"""
    try:
        return db_service.list_canvases()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list canvases: {str(e)}"
        )

@router.post("/create")
async def create_canvas(request: Request):
    """Create a new canvas for the authenticated user"""
    try:
        data = await request.json()
        id = data.get('canvas_id')
        name = data.get('name')

        if not id or not name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="canvas_id and name are required"
            )

        asyncio.create_task(handle_chat(data))
        db_service.create_canvas(id, name)
        return {"id": id}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create canvas: {str(e)}"
        )

@router.get("/{id}")
async def get_canvas(id: str):
    """Get canvas data for the authenticated user"""
    try:
        canvas_data = db_service.get_canvas_data(id)
        if not canvas_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Canvas not found or access denied"
            )
        return canvas_data
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get canvas: {str(e)}"
        )

@router.post("/{id}/save")
async def save_canvas(id: str, request: Request):
    """Save canvas data for the authenticated user"""
    try:
        payload = await request.json()
        if 'data' not in payload:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="data field is required"
            )

        data_str = json.dumps(payload['data'])
        thumbnail = payload.get('thumbnail')
        db_service.save_canvas_data(id, data_str, thumbnail)
        return {"id": id}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save canvas: {str(e)}"
        )

@router.post("/{id}/rename")
async def rename_canvas(id: str, request: Request):
    """Rename canvas for the authenticated user"""
    try:
        data = await request.json()
        name = data.get('name')
        if not name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="name field is required"
            )

        db_service.rename_canvas(id, name)
        return {"id": id}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rename canvas: {str(e)}"
        )

@router.delete("/{id}/delete")
async def delete_canvas(id: str):
    """Delete canvas for the authenticated user"""
    try:
        db_service.delete_canvas(id)
        return {"id": id}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete canvas: {str(e)}"
        )