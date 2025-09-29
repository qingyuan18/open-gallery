from typing import List, Dict, Any, Optional
from .database_interface import DatabaseFactory, DatabaseInterface
from .config_service import config_service

class UnifiedDatabaseService:
    """Unified database service that uses DynamoDB only"""

    def __init__(self):
        self.primary_db: DatabaseInterface = None
        self._initialize_database()

    def _initialize_database(self):
        """Initialize DynamoDB as the only database"""
        db_config = config_service.get_database_config()

        try:
            print("Initializing DynamoDB as primary database")
            dynamodb_config = db_config.get('dynamodb', {})
            self.primary_db = DatabaseFactory.create_database(
                'dynamodb',
                region_name=dynamodb_config.get('region', 'us-west-2')
            )
        except Exception as e:
            print(f"Error initializing DynamoDB: {e}")
            raise e
    
    def _execute_operation(self, operation_name: str, *args, **kwargs):
        """Execute database operation on DynamoDB"""
        try:
            method = getattr(self.primary_db, operation_name)
            return method(*args, **kwargs)
        except Exception as error:
            print(f"Database operation {operation_name} failed: {error}")
            raise error
    
    # Canvas operations
    def create_canvas(self, id: str, name: str):
        """Create a new canvas"""
        return self._execute_operation('create_canvas', id, name)

    def list_canvases(self) -> List[Dict[str, Any]]:
        """Get all canvases"""
        return self._execute_operation('list_canvases')

    def get_canvas(self, id: str) -> Optional[Dict[str, Any]]:
        """Get canvas by ID"""
        return self._execute_operation('get_canvas', id)

    def save_canvas_data(self, id: str, data: str, thumbnail: str = None):
        """Save canvas data"""
        return self._execute_operation('save_canvas_data', id, data, thumbnail)

    def rename_canvas(self, id: str, name: str):
        """Rename canvas"""
        return self._execute_operation('rename_canvas', id, name)

    def delete_canvas(self, id: str):
        """Delete canvas"""
        return self._execute_operation('delete_canvas', id)
    
    # Chat session operations
    def create_chat_session(self, id: str, model: str, provider: str, canvas_id: str, title: Optional[str] = None):
        """Save a new chat session"""
        return self._execute_operation('create_chat_session', id, model, provider, canvas_id, title)

    def list_chat_sessions(self, canvas_id: str) -> List[Dict[str, Any]]:
        """Get chat sessions for a canvas"""
        return self._execute_operation('list_chat_sessions', canvas_id)

    def get_chat_session(self, id: str) -> Optional[Dict[str, Any]]:
        """Get chat session by ID"""
        return self._execute_operation('get_chat_session', id)

    def update_chat_session_title(self, id: str, title: str):
        """Update chat session title"""
        return self._execute_operation('update_chat_session_title', id, title)

    def delete_chat_session(self, id: str):
        """Delete chat session"""
        return self._execute_operation('delete_chat_session', id)
    
    # Chat message operations
    def create_message(self, session_id: str, role: str, message: str):
        """Save a chat message"""
        return self._execute_operation('create_message', session_id, role, message)

    def list_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get messages for a chat session"""
        return self._execute_operation('list_messages', session_id)

    # ComfyUI workflow operations
    def create_comfy_workflow(self, name: str, api_json: str, description: str, inputs: str, outputs: str = None):
        """Create a new comfy workflow"""
        return self._execute_operation('create_comfy_workflow', name, api_json, description, inputs, outputs)

    def list_comfy_workflows(self) -> List[Dict[str, Any]]:
        """List all comfy workflows"""
        return self._execute_operation('list_comfy_workflows')

    def get_comfy_workflow(self, id: int) -> Optional[Dict[str, Any]]:
        """Get comfy workflow by ID"""
        return self._execute_operation('get_comfy_workflow', id)

    def delete_comfy_workflow(self, id: int):
        """Delete a comfy workflow"""
        return self._execute_operation('delete_comfy_workflow', id)
    
    # File operations
    def create_file(self, file_id: str, file_path: str, width: int = None, height: int = None):
        """Create a new file record"""
        return self._execute_operation('create_file', file_id, file_path, width, height)

    def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file record by ID"""
        return self._execute_operation('get_file', file_id)

    def list_files(self) -> List[Dict[str, Any]]:
        """List all files"""
        return self._execute_operation('list_files')

    def delete_file(self, file_id: str):
        """Delete a file record"""
        return self._execute_operation('delete_file', file_id)

    # Database version operations
    def get_db_version(self) -> int:
        """Get current database version"""
        return self._execute_operation('get_db_version')

    def set_db_version(self, version: int):
        """Set database version"""
        return self._execute_operation('set_db_version', version)

# Create a singleton instance
unified_db_service = UnifiedDatabaseService()
