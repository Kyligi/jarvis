
"""Gestion locale des souvenirs personnels de Jarvis."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from jarvis.memory.database import DB
from jarvis.memory.schema import initialize_memory
from jarvis.persistence.sqlite import connect


@dataclass(frozen=True)
class Memory:
    id: int
    content: str
    category: str
    source: str
    created_at: str
    updated_at: str


class MemoryService:
    CATEGORIES = {
        "general",
        "preferences",
        "projects",
        "habits",
        "instructions",
    }

    def __init__(self, db_path: Path = DB):
        self.db_path = Path(db_path)
        initialize_memory(self.db_path)

    def _validate_content(self, content: str) -> str:
        if not isinstance(content, str):
            raise ValueError("Le souvenir doit être du texte.")

        content = " ".join(content.split())

        if not content or len(content) > 2000:
            raise ValueError(
                "Le souvenir doit contenir entre 1 et 2000 caractères."
            )

        return content

    @staticmethod
    def _row_to_memory(row: tuple) -> Memory:
        return Memory(*row)

    def add_memory(
        self,
        content: str,
        category: str = "general",
        source: str = "explicit",
    ) -> Memory:
        content = self._validate_content(content)

        if category not in self.CATEGORIES:
            raise ValueError("Catégorie invalide.")

        if source != "explicit":
            raise ValueError("La mémorisation doit être explicite.")

        now = datetime.now(timezone.utc).isoformat()

        with connect(self.db_path) as con:
            existing = con.execute(
                """
                SELECT id, content, category, source,
                       created_at, updated_at
                FROM memories
                WHERE content = ? COLLATE NOCASE
                  AND category = ?
                LIMIT 1
                """,
                (content, category),
            ).fetchone()

            if existing:
                return self._row_to_memory(existing)

            cursor = con.execute(
                """
                INSERT INTO memories(
                    content, category, source,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (content, category, source, now, now),
            )

            row = con.execute(
                """
                SELECT id, content, category, source,
                       created_at, updated_at
                FROM memories WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()

        return self._row_to_memory(row)

    def get_memory(self, memory_id: int) -> Memory | None:
        with connect(self.db_path) as con:
            row = con.execute(
                """
                SELECT id, content, category, source,
                       created_at, updated_at
                FROM memories WHERE id = ?
                """,
                (memory_id,),
            ).fetchone()

        return self._row_to_memory(row) if row else None

    def list_memories(
        self, category: str | None = None
    ) -> list[Memory]:
        query = """
            SELECT id, content, category, source,
                   created_at, updated_at
            FROM memories
        """
        params = ()

        if category is not None:
            if category not in self.CATEGORIES:
                raise ValueError("Catégorie invalide.")

            query += " WHERE category = ?"
            params = (category,)

        query += " ORDER BY updated_at DESC, id DESC"

        with connect(self.db_path) as con:
            rows = con.execute(query, params).fetchall()

        return [self._row_to_memory(row) for row in rows]

    def update_memory(
        self, memory_id: int, content: str
    ) -> Memory | None:
        content = self._validate_content(content)
        now = datetime.now(timezone.utc).isoformat()

        with connect(self.db_path) as con:
            cursor = con.execute(
                """
                UPDATE memories
                SET content = ?, updated_at = ?
                WHERE id = ?
                """,
                (content, now, memory_id),
            )

            if cursor.rowcount == 0:
                return None

        return self.get_memory(memory_id)

    def delete_memory(self, memory_id: int) -> bool:
        with connect(self.db_path) as con:
            cursor = con.execute(
                "DELETE FROM memories WHERE id = ?",
                (memory_id,),
            )

        return cursor.rowcount > 0

    def clear_memories(self) -> int:
        """Supprime les souvenirs, sans toucher à l'historique."""
        with connect(self.db_path) as con:
            count = con.execute(
                "SELECT COUNT(*) FROM memories"
            ).fetchone()[0]

            con.execute("DELETE FROM memories")

        return count
