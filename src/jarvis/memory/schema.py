
"""Schéma SQLite pour la mémoire personnelle de Jarvis V1.6."""

from pathlib import Path

from jarvis.memory.database import DB
from jarvis.persistence.sqlite import connect
import sqlite3

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

        # Index de recherche textuelle FTS5.
        # Les souvenirs restent stockés dans la table memories.
        try:
            exists = con.execute(
                """
                SELECT 1 FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'memories_fts'
                """
            ).fetchone()

            con.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
                USING fts5(
                    content,
                    content='memories',
                    content_rowid='id',
                    tokenize='unicode61 remove_diacritics 2'
                )
            """)

            # Synchronisation automatique lors d'un ajout.
            con.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_fts_insert
                AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(rowid, content)
                    VALUES (new.id, new.content);
                END
            """)

            # Synchronisation lors d'une suppression.
            con.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_fts_delete
                AFTER DELETE ON memories BEGIN
                    INSERT INTO memories_fts(
                        memories_fts, rowid, content
                    )
                    VALUES ('delete', old.id, old.content);
                END
            """)

            # Synchronisation lors d'une modification.
            con.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_fts_update
                AFTER UPDATE ON memories BEGIN
                    INSERT INTO memories_fts(
                        memories_fts, rowid, content
                    )
                    VALUES ('delete', old.id, old.content);

                    INSERT INTO memories_fts(rowid, content)
                    VALUES (new.id, new.content);
                END
            """)

            # Indexer les souvenirs antérieurs une seule fois
            # lors de la création initiale de l'index.
            if not exists:
                con.execute("""
                    INSERT INTO memories_fts(memories_fts)
                    VALUES ('rebuild')
                """)

        except sqlite3.OperationalError as error:
            # SQLite peut être compilé sans FTS5.
            # Les autres erreurs doivent rester visibles.
            if "no such module: fts5" not in str(error).lower():
                raise
