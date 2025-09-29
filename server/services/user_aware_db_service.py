"""
User-aware database service that enforces user isolation
"""
from typing import List, Dict, Any, Optional
from .dynamodb_service import DynamoDBService


class UserAwareDatabaseService:
    """Database service that enforces user-level data isolation"""
    
    def __init__(self, region_name='us-west-2'):
        self.db_service = DynamoDBService(region_name=region_name)
    
    # Canvas operations
    def create_canvas(self, id: str, name: str, user_id: str):
        """Create a new canvas for a specific user"""
        return self.db_service.create_canvas(id, name, user_id)

    def list_canvases(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all canvases for a specific user"""
        return self.db_service.list_canvases(user_id)

    def get_canvas(self, id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get canvas by ID with user verification"""
        return self.db_service.get_canvas(id, user_id)

    def save_canvas_data(self, id: str, data: str, user_id: str, thumbnail: str = None):
        """Save canvas data with user verification"""
        return self.db_service.save_canvas_data(id, data, user_id, thumbnail)

    def rename_canvas(self, id: str, name: str, user_id: str):
        """Rename canvas with user verification"""
        return self.db_service.rename_canvas(id, name, user_id)

    def delete_canvas(self, id: str, user_id: str):
        """Delete canvas with user verification"""
        return self.db_service.delete_canvas(id, user_id)
    
    # Chat session operations
    def create_chat_session(self, id: str, model: str, provider: str, canvas_id: str, user_id: str, title: Optional[str] = None):
        """Save a new chat session for a specific user"""
        return self.db_service.create_chat_session(id, model, provider, canvas_id, user_id, title)

    def list_chat_sessions(self, canvas_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Get chat sessions for a canvas with user verification"""
        return self.db_service.list_chat_sessions(canvas_id, user_id)

    def list_user_chat_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all chat sessions for a user"""
        return self.db_service.list_user_chat_sessions(user_id)

    def get_chat_session(self, id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get chat session by ID with user verification"""
        return self.db_service.get_chat_session(id, user_id)

    def update_chat_session_title(self, id: str, title: str, user_id: str):
        """Update chat session title with user verification"""
        return self.db_service.update_chat_session_title(id, title, user_id)

    def delete_chat_session(self, id: str, user_id: str):
        """Delete chat session with user verification"""
        return self.db_service.delete_chat_session(id, user_id)
    
    # Chat message operations
    def create_message(self, session_id: str, role: str, message: str, user_id: str):
        """Save a chat message with user verification"""
        return self.db_service.create_message(session_id, role, message, user_id)

    def list_messages(self, session_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Get messages for a chat session with user verification"""
        return self.db_service.list_messages(session_id, user_id)

    # ComfyUI workflow operations
    def create_comfy_workflow(self, name: str, api_json: str, description: str, inputs: str, user_id: str, outputs: str = None):
        """Create a new comfy workflow for a specific user"""
        return self.db_service.create_comfy_workflow(name, api_json, description, inputs, user_id, outputs)

    def list_comfy_workflows(self, user_id: str) -> List[Dict[str, Any]]:
        """List comfy workflows for a specific user"""
        return self.db_service.list_comfy_workflows(user_id)

    def get_comfy_workflow(self, id: int, user_id: str) -> Optional[Dict[str, Any]]:
        """Get comfy workflow by ID with user verification"""
        return self.db_service.get_comfy_workflow(id, user_id)

    def delete_comfy_workflow(self, id: int, user_id: str):
        """Delete a comfy workflow with user verification"""
        return self.db_service.delete_comfy_workflow(id, user_id)

    # File operations
    def create_file(self, file_id: str, file_path: str, user_id: str, width: int = None, height: int = None):
        """Create a new file record for a specific user"""
        return self.db_service.create_file(file_id, file_path, user_id, width, height)

    def get_file(self, file_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get file record by ID with user verification"""
        return self.db_service.get_file(file_id, user_id)

    def list_files(self, user_id: str) -> List[Dict[str, Any]]:
        """List files for a specific user"""
        return self.db_service.list_files(user_id)

    def delete_file(self, file_id: str, user_id: str):
        """Delete a file record with user verification"""
        return self.db_service.delete_file(file_id, user_id)

    # Database version operations (no user isolation needed)
    def get_db_version(self) -> int:
        """Get current database version"""
        return self.db_service.get_db_version()

    def set_db_version(self, version: int):
        """Set database version"""
        return self.db_service.set_db_version(version)


# Create a global instance
user_aware_db_service = UserAwareDatabaseService()
