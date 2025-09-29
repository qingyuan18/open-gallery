import sqlite3
import aiosqlite
from typing import List, Dict, Any, Optional
from .database_interface import DatabaseInterface
from .config_service import USER_DATA_DIR
from .migrations.manager import MigrationManager
import os

# Database version
CURRENT_VERSION = 4

class SQLiteAdapter(DatabaseInterface):
    """SQLite adapter implementing the database interface"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(USER_DATA_DIR, "localmanus.db")
        
        self.db_path = db_path
        self._ensure_db_directory()
        self._migration_manager = MigrationManager()
        self._init_db()
    
    def _ensure_db_directory(self):
        """Ensure the database directory exists"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    def _init_db(self):
        """Initialize the database with the current schema"""
        with sqlite3.connect(self.db_path) as conn:
            # Create version table if it doesn't exist
            conn.execute("""
                CREATE TABLE IF NOT EXISTS db_version (
                    version INTEGER PRIMARY KEY
                )
            """)
            
            # Get current version
            cursor = conn.execute("SELECT version FROM db_version")
            current_version = cursor.fetchone()
            print('local db version', current_version, 'latest version', CURRENT_VERSION)
            
            if current_version is None:
                # First time setup - start from version 0
                conn.execute("INSERT INTO db_version (version) VALUES (0)")
                self._migration_manager.migrate(conn, 0, CURRENT_VERSION)
            elif current_version[0] < CURRENT_VERSION:
                print('Migrating database from version', current_version[0], 'to', CURRENT_VERSION)
                # Need to migrate
                self._migration_manager.migrate(conn, current_version[0], CURRENT_VERSION)
    
    # Canvas operations
    async def create_canvas(self, id: str, name: str):
        """Create a new canvas"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO canvases (id, name)
                VALUES (?, ?)
            """, (id, name))
            await db.commit()
    
    async def list_canvases(self) -> List[Dict[str, Any]]:
        """Get all canvases"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute("""
                SELECT id, name, description, thumbnail, created_at, updated_at
                FROM canvases
                ORDER BY updated_at DESC
            """)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_canvas(self, id: str) -> Optional[Dict[str, Any]]:
        """Get canvas by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute("""
                SELECT id, name, description, thumbnail, data, created_at, updated_at
                FROM canvases
                WHERE id = ?
            """, (id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def save_canvas_data(self, id: str, data: str, thumbnail: str = None):
        """Save canvas data"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE canvases 
                SET data = ?, thumbnail = ?, updated_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ?
            """, (data, thumbnail, id))
            await db.commit()
    
    async def rename_canvas(self, id: str, name: str):
        """Rename canvas"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE canvases SET name = ? WHERE id = ?", (name, id))
            await db.commit()
    
    async def delete_canvas(self, id: str):
        """Delete canvas"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM canvases WHERE id = ?", (id,))
            await db.commit()
    
    # Chat session operations
    async def create_chat_session(self, id: str, model: str, provider: str, canvas_id: str, title: Optional[str] = None):
        """Save a new chat session"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO chat_sessions (id, model, provider, canvas_id, title)
                VALUES (?, ?, ?, ?, ?)
            """, (id, model, provider, canvas_id, title))
            await db.commit()
    
    async def list_chat_sessions(self, canvas_id: str) -> List[Dict[str, Any]]:
        """Get chat sessions for a canvas"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute("""
                SELECT id, model, provider, canvas_id, title, created_at, updated_at
                FROM chat_sessions
                WHERE canvas_id = ?
                ORDER BY updated_at DESC
            """, (canvas_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_chat_session(self, id: str) -> Optional[Dict[str, Any]]:
        """Get chat session by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute("""
                SELECT id, model, provider, canvas_id, title, created_at, updated_at
                FROM chat_sessions
                WHERE id = ?
            """, (id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def update_chat_session_title(self, id: str, title: str):
        """Update chat session title"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE chat_sessions 
                SET title = ?, updated_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ?
            """, (title, id))
            await db.commit()
    
    async def delete_chat_session(self, id: str):
        """Delete chat session"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM chat_sessions WHERE id = ?", (id,))
            await db.commit()
    
    # Chat message operations
    async def create_message(self, session_id: str, role: str, message: str):
        """Save a chat message"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO chat_messages (session_id, role, message)
                VALUES (?, ?, ?)
            """, (session_id, role, message))
            await db.commit()
    
    async def list_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get messages for a chat session"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute("""
                SELECT id, session_id, role, message, created_at, updated_at
                FROM chat_messages
                WHERE session_id = ?
                ORDER BY id ASC
            """, (session_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # ComfyUI workflow operations
    async def create_comfy_workflow(self, name: str, api_json: str, description: str, inputs: str, outputs: str = None):
        """Create a new comfy workflow"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO comfy_workflows (name, api_json, description, inputs, outputs)
                VALUES (?, ?, ?, ?, ?)
            """, (name, api_json, description, inputs, outputs))
            await db.commit()

    async def list_comfy_workflows(self) -> List[Dict[str, Any]]:
        """List all comfy workflows"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute("""
                SELECT id, name, api_json, description, inputs, outputs, created_at, updated_at
                FROM comfy_workflows
                ORDER BY updated_at DESC
            """)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_comfy_workflow(self, id: int) -> Optional[Dict[str, Any]]:
        """Get comfy workflow by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute("""
                SELECT id, name, api_json, description, inputs, outputs, created_at, updated_at
                FROM comfy_workflows
                WHERE id = ?
            """, (id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def delete_comfy_workflow(self, id: int):
        """Delete a comfy workflow"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM comfy_workflows WHERE id = ?", (id,))
            await db.commit()

    # File operations
    async def create_file(self, file_id: str, file_path: str, width: int = None, height: int = None):
        """Create a new file record"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO files (id, file_path, width, height)
                VALUES (?, ?, ?, ?)
            """, (file_id, file_path, width, height))
            await db.commit()

    async def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file record by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute("""
                SELECT id, file_path, width, height, created_at, updated_at
                FROM files
                WHERE id = ?
            """, (file_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def list_files(self) -> List[Dict[str, Any]]:
        """List all files"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute("""
                SELECT id, file_path, width, height, created_at, updated_at
                FROM files
                ORDER BY created_at DESC
            """)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def delete_file(self, file_id: str):
        """Delete a file record"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM files WHERE id = ?", (file_id,))
            await db.commit()

    # Database version operations
    async def get_db_version(self) -> int:
        """Get current database version"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT version FROM db_version")
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def set_db_version(self, version: int):
        """Set database version"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE db_version SET version = ?", (version,))
            await db.commit()
