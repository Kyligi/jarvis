
"""Gestion des conversations persistantes de Jarvis V1.6."""
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from jarvis.memory.conversation_store import initialize_conversations
from jarvis.memory.database import DB
from jarvis.persistence.sqlite import connect


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ConversationRecord:
    id: int
    title: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class MessageRecord:
    id: int
    conversation_id: int
    role: str
    content: str
    created_at: str


class ConversationService:
    """Stockage local des discussions, désactivable à tout moment."""

    def __init__(
        self,
        db_path: Path = DB,
        enabled: bool = True,
    ):
        self.db_path = Path(db_path)
        self.enabled = enabled

        if self.enabled:
            initialize_conversations(self.db_path)

    @staticmethod
    def _validate_text(text: str, max_length: int) -> str:
        if not isinstance(text, str):
            raise ValueError("Le contenu doit être du texte.")

        text = text.strip()

        if not text or len(text) > max_length:
            raise ValueError(
                f"Le texte doit contenir entre 1 et {max_length} caractères."
            )

        return text

    @staticmethod
    def _conversation(row) -> ConversationRecord:
        return ConversationRecord(*row)

    @staticmethod
    def _message(row) -> MessageRecord:
        return MessageRecord(*row)

    def create_conversation(
        self,
        title: str = "Nouvelle conversation",
    ) -> ConversationRecord | None:
        if not self.enabled:
            return None

        title = self._validate_text(title, 200)
        now = utc_now()

        with connect(self.db_path) as con:
            cursor = con.execute(
                """
                INSERT INTO conversations(
                    title, created_at, updated_at
                )
                VALUES (?, ?, ?)
                """,
                (title, now, now),
            )

            conversation_id = cursor.lastrowid

            row = con.execute(
                """
                SELECT id, title, created_at, updated_at
                FROM conversations WHERE id = ?
                """,
                (conversation_id,),
            ).fetchone()

        return self._conversation(row)

    def get_conversation(
        self, conversation_id: int
    ) -> ConversationRecord | None:
        if not self.enabled:
            return None

        with connect(self.db_path) as con:
            row = con.execute(
                """
                SELECT id, title, created_at, updated_at
                FROM conversations WHERE id = ?
                """,
                (conversation_id,),
            ).fetchone()

        return self._conversation(row) if row else None

    def list_conversations(self) -> list[ConversationRecord]:
        if not self.enabled:
            return []

        with connect(self.db_path) as con:
            rows = con.execute(
                """
                SELECT id, title, created_at, updated_at
                FROM conversations
                ORDER BY updated_at DESC, id DESC
                """
            ).fetchall()

        return [self._conversation(row) for row in rows]

    def rename_conversation(
        self,
        conversation_id: int,
        title: str,
    ) -> ConversationRecord | None:
        if not self.enabled:
            return None

        title = self._validate_text(title, 200)

        with connect(self.db_path) as con:
            cursor = con.execute(
                """
                UPDATE conversations
                SET title = ?, updated_at = ?
                WHERE id = ?
                """,
                (title, utc_now(), conversation_id),
            )

            if cursor.rowcount == 0:
                return None

        return self.get_conversation(conversation_id)

    def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
    ) -> MessageRecord | None:
        if not self.enabled:
            return None

        if role not in ("user", "assistant"):
            raise ValueError("Rôle de message invalide.")

        content = self._validate_text(content, 20000)
        now = utc_now()

        with connect(self.db_path) as con:
            # Vérification explicite de la conversation :
            # aucune insertion orpheline n'est autorisée.
            exists = con.execute(
                "SELECT 1 FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()

            if not exists:
                raise ValueError("Conversation inexistante.")

            cursor = con.execute(
                """
                INSERT INTO messages(
                    conversation_id, role, content, created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (conversation_id, role, content, now),
            )

            con.execute(
                """
                UPDATE conversations
                SET updated_at = ?
                WHERE id = ?
                """,
                (now, conversation_id),
            )

            row = con.execute(
                """
                SELECT id, conversation_id, role,
                       content, created_at
                FROM messages WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()

        return self._message(row)


    def add_turn(
        self,
        conversation_id: int,
        user_text: str,
        assistant_text: str,
    ) -> bool:
        """Enregistre un échange complet dans une seule transaction."""

        if not self.enabled:
            return False

        user_text = self._validate_text(user_text, 20000)
        assistant_text = self._validate_text(assistant_text, 20000)

        now = utc_now()

        with connect(self.db_path) as con:
            exists = con.execute(
                "SELECT 1 FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()

            if exists is None:
                raise ValueError("Conversation inexistante.")

            con.executemany(
                """
                INSERT INTO messages(
                    conversation_id, role, content, created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                [
                    (conversation_id, "user", user_text, now),
                    (conversation_id, "assistant", assistant_text, now),
                ],
            )

            con.execute(
                """
                UPDATE conversations
                SET updated_at = ?
                WHERE id = ?
                """,
                (now, conversation_id),
            )

        return True

    def get_messages(
        self, conversation_id: int
    ) -> list[MessageRecord]:
        if not self.enabled:
            return []

        with connect(self.db_path) as con:
            rows = con.execute(
                """
                SELECT id, conversation_id, role,
                       content, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY id ASC
                """,
                (conversation_id,),
            ).fetchall()

        return [self._message(row) for row in rows]

    def delete_conversation(self, conversation_id: int) -> bool:
        if not self.enabled:
            return False

        with connect(self.db_path) as con:
            # Suppression explicite des messages dans
            # la même transaction, même si foreign_keys
            # n'est pas activé dans SQLite.
            con.execute(
                "DELETE FROM messages WHERE conversation_id = ?",
                (conversation_id,),
            )

            cursor = con.execute(
                "DELETE FROM conversations WHERE id = ?",
                (conversation_id,),
            )

        return cursor.rowcount > 0

    def set_enabled(self, enabled: bool) -> None:
        if not isinstance(enabled, bool):
            raise ValueError("L'état doit être un booléen.")

        if enabled and not self.enabled:
            initialize_conversations(self.db_path)

        self.enabled = enabled
