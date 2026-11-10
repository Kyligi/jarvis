
"""Tests des conversations persistantes de Jarvis V1.6."""

import sqlite3

import pytest

from jarvis.memory.conversation_service import ConversationService
from jarvis.memory.service import MemoryService


@pytest.fixture
def service(tmp_path):
    return ConversationService(tmp_path / "memory.sqlite3")


def test_create_conversation(service):
    conversation = service.create_conversation("Discussion Python")

    assert conversation is not None
    assert conversation.title == "Discussion Python"
    assert conversation.id > 0
    assert service.get_conversation(conversation.id) == conversation


def test_add_messages(service):
    conversation = service.create_conversation()

    user = service.add_message(
        conversation.id, "user", "Bonjour Jarvis"
    )
    assistant = service.add_message(
        conversation.id, "assistant", "Bonjour !"
    )

    messages = service.get_messages(conversation.id)

    assert [message.id for message in messages] == [
        user.id, assistant.id
    ]
    assert [message.role for message in messages] == [
        "user", "assistant"
    ]


def test_persistence_after_restart(tmp_path):
    db = tmp_path / "memory.sqlite3"

    first = ConversationService(db)
    conversation = first.create_conversation("Rust")
    first.add_message(conversation.id, "user", "Apprendre Rust")

    restarted = ConversationService(db)

    assert restarted.get_conversation(conversation.id) is not None
    assert len(restarted.get_messages(conversation.id)) == 1


def test_rename_conversation(service):
    conversation = service.create_conversation("Ancien titre")

    renamed = service.rename_conversation(
        conversation.id, "Nouveau titre"
    )

    assert renamed.title == "Nouveau titre"
    assert len(service.list_conversations()) == 1


def test_delete_cascades_messages(service):
    conversation = service.create_conversation()
    service.add_message(conversation.id, "user", "Message temporaire")

    assert service.delete_conversation(conversation.id)
    assert service.get_conversation(conversation.id) is None
    assert service.get_messages(conversation.id) == []

    with sqlite3.connect(service.db_path) as con:
        count = con.execute(
            "SELECT COUNT(*) FROM messages WHERE conversation_id = ?",
            (conversation.id,),
        ).fetchone()[0]

    assert count == 0


def test_conversation_isolation(service):
    first = service.create_conversation("Première")
    second = service.create_conversation("Deuxième")

    service.add_message(first.id, "user", "Message A")
    service.add_message(second.id, "user", "Message B")

    assert service.get_messages(first.id)[0].content == "Message A"
    assert service.get_messages(second.id)[0].content == "Message B"


def test_disabled_service(tmp_path):
    db = tmp_path / "memory.sqlite3"
    service = ConversationService(db, enabled=False)

    assert service.create_conversation() is None
    assert service.list_conversations() == []
    assert service.get_messages(1) == []

    service.set_enabled(True)
    assert service.create_conversation() is not None


@pytest.mark.parametrize("role", [
    "system",
    "tool",
    "developer",
    "",
])
def test_reject_unsafe_roles(service, role):
    conversation = service.create_conversation()

    with pytest.raises(ValueError):
        service.add_message(conversation.id, role, "Texte")


@pytest.mark.parametrize("content", [
    "",
    " ",
    "x" * 20001,
])
def test_reject_invalid_messages(service, content):
    conversation = service.create_conversation()

    with pytest.raises(ValueError):
        service.add_message(conversation.id, "user", content)


def test_reject_orphan_message(service):
    with pytest.raises(ValueError):
        service.add_message(999999, "user", "Message orphelin")


def test_memory_preserved(tmp_path):
    db = tmp_path / "memory.sqlite3"

    memory = MemoryService(db)
    memory.add_memory("Je préfère Rust")

    conversations = ConversationService(db)
    discussion = conversations.create_conversation()
    conversations.add_message(discussion.id, "user", "Bonjour")
    conversations.delete_conversation(discussion.id)

    assert len(memory.list_memories()) == 1
