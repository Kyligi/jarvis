"""Gestion locale des souvenirs personnels de Jarvis."""
import re
import unicodedata
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

    @staticmethod
    def _normalize_search(text: str) -> str:
        """Normalise la casse et les accents."""
        text = unicodedata.normalize("NFKD", text.casefold())
        return "".join(
            char for char in text
            if not unicodedata.combining(char)
        )

    def search_memories(
        self,
        query: str,
        limit: int = 5,
    ) -> list[Memory]:
        """Recherche les souvenirs sans modifier la base."""

        if not isinstance(query, str):
            raise ValueError("La recherche doit être du texte.")

        if not isinstance(limit, int) or isinstance(limit, bool):
            raise ValueError("Limite invalide.")

        if not 1 <= limit <= 50:
            raise ValueError("La limite doit être entre 1 et 50.")

        tokens = re.findall(r"\w+", query, flags=re.UNICODE)
        tokens = [
            self._normalize_search(token)
            for token in tokens
        ]
        tokens = [token for token in tokens if token]

        if not tokens:
            return []

        # Recherche FTS5 : mots entiers, classés avec bm25.
        # Paramétrage SQL obligatoire : aucune interpolation
        # directe de la requête utilisateur dans le SQL.
        fts_query = " OR ".join(
            f'"{token}"' for token in tokens[:12]
        )

        try:
            with connect(self.db_path) as con:
                rows = con.execute(
                    """
                    SELECT m.id, m.content, m.category,
                           m.source, m.created_at, m.updated_at
                    FROM memories_fts
                    JOIN memories AS m
                      ON m.id = memories_fts.rowid
                    WHERE memories_fts MATCH ?
                    ORDER BY bm25(memories_fts),
                             m.updated_at DESC
                    LIMIT ?
                    """,
                    (fts_query, limit),
                ).fetchall()

            return [self._row_to_memory(row) for row in rows]

        except sqlite3.OperationalError as error:
            message = str(error).lower()
            if not (
                "no such table: memories_fts" in message
                or "no such module: fts5" in message
                or "no such function: bm25" in message
            ):
                raise

        # Recherche de secours si FTS5 est indisponible.
        # Convient à une mémoire personnelle de taille modérée.
        memories = self.list_memories()
        scored = []

        for memory in memories:
            normalized = self._normalize_search(memory.content)
            words = set(re.findall(r"\w+", normalized))

            score = sum(
                1 for token in tokens if token in words
            )

            if score:
                scored.append((score, memory))

        scored.sort(
            key=lambda item: (
                item[0],
                item[1].updated_at,
                item[1].id,
            ),
            reverse=True,
        )

        return [
            memory for _, memory in scored[:limit]
        ]

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
