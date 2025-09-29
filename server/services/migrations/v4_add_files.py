from . import Migration
import sqlite3


class V4AddFiles(Migration):
    version = 4
    description = "Add files table"

    def up(self, conn: sqlite3.Connection) -> None:
        # Create files table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                width INTEGER,
                height INTEGER,
                created_at TEXT DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')),
                updated_at TEXT DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_files_created_at ON files(created_at DESC, id DESC)
        """)

    def down(self, conn: sqlite3.Connection) -> None:
        conn.execute("DROP TABLE IF EXISTS files")
