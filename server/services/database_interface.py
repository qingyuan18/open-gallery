from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class DatabaseInterface(ABC):
    """Abstract interface for database operations"""
    
    # Canvas operations
    @abstractmethod
    def create_canvas(self, id: str, name: str):
        """Create a new canvas"""
        pass

    @abstractmethod
    def list_canvases(self) -> List[Dict[str, Any]]:
        """Get all canvases"""
        pass

    @abstractmethod
    def get_canvas(self, id: str) -> Optional[Dict[str, Any]]:
        """Get canvas by ID"""
        pass

    @abstractmethod
    def save_canvas_data(self, id: str, data: str, thumbnail: str = None):
        """Save canvas data"""
        pass

    @abstractmethod
    def rename_canvas(self, id: str, name: str):
        """Rename canvas"""
        pass

    @abstractmethod
    def delete_canvas(self, id: str):
        """Delete canvas"""
        pass
    
    # Chat session operations
    @abstractmethod
    def create_chat_session(self, id: str, model: str, provider: str, canvas_id: str, title: Optional[str] = None):
        """Save a new chat session"""
        pass

    @abstractmethod
    def list_chat_sessions(self, canvas_id: str) -> List[Dict[str, Any]]:
        """Get chat sessions for a canvas"""
        pass

    @abstractmethod
    def get_chat_session(self, id: str) -> Optional[Dict[str, Any]]:
        """Get chat session by ID"""
        pass

    @abstractmethod
    def update_chat_session_title(self, id: str, title: str):
        """Update chat session title"""
        pass

    @abstractmethod
    def delete_chat_session(self, id: str):
        """Delete chat session"""
        pass
    
    # Chat message operations
    @abstractmethod
    def create_message(self, session_id: str, role: str, message: str):
        """Save a chat message"""
        pass

    @abstractmethod
    def list_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get messages for a chat session"""
        pass

    # ComfyUI workflow operations
    @abstractmethod
    def create_comfy_workflow(self, name: str, api_json: str, description: str, inputs: str, outputs: str = None):
        """Create a new comfy workflow"""
        pass

    @abstractmethod
    def list_comfy_workflows(self) -> List[Dict[str, Any]]:
        """List all comfy workflows"""
        pass

    @abstractmethod
    def get_comfy_workflow(self, id: int) -> Optional[Dict[str, Any]]:
        """Get comfy workflow by ID"""
        pass

    @abstractmethod
    def delete_comfy_workflow(self, id: int):
        """Delete a comfy workflow"""
        pass
    
    # File operations
    @abstractmethod
    def create_file(self, file_id: str, file_path: str, width: int = None, height: int = None):
        """Create a new file record"""
        pass

    @abstractmethod
    def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file record by ID"""
        pass

    @abstractmethod
    def list_files(self) -> List[Dict[str, Any]]:
        """List all files"""
        pass

    @abstractmethod
    def delete_file(self, file_id: str):
        """Delete a file record"""
        pass

    # Database version operations
    @abstractmethod
    def get_db_version(self) -> int:
        """Get current database version"""
        pass

    @abstractmethod
    def set_db_version(self, version: int):
        """Set database version"""
        pass


class DatabaseFactory:
    """Factory class to create database instances"""
    
    @staticmethod
    def create_database(db_type: str = "sqlite", **kwargs) -> DatabaseInterface:
        """Create database instance based on type"""
        if db_type.lower() == "dynamodb":
            from .dynamodb_adapter import DynamoDBAdapter
            return DynamoDBAdapter(**kwargs)
        elif db_type.lower() == "sqlite":
            from .sqlite_adapter import SQLiteAdapter
            return SQLiteAdapter(**kwargs)
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
