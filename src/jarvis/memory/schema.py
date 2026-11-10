
"""Schéma SQLite pour la mémoire personnelle de Jarvis V1.6."""

from pathlib import Path

from jarvis.memory.database import DB
from jarvis.persistence.sqlite import connect


def initialize_memory(db_path: Path = DB) -> None:
    """Crée les tables de mémoire sans effacer les données existantes."""

    with connect(db_path) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'general',
                source TEXT NOT NULL DEFAULT 'explicit',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_category
            ON memories(category)
        """)
