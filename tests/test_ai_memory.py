
"""Tests V1.6 : persistance automatique des échanges IA."""

import json

from jarvis.ai.config import AIConfig
from jarvis.ai.conversation import Conversation, object_schema
from jarvis.ai.tools import Tool
from jarvis.memory.conversation_service import ConversationService


class FakeBackend:
    def __init__(self, reply="Bonjour !", calls=None):
        self.reply = reply
        self.calls = calls if calls is not None else []

    def generate(
        self, config, messages, schema, cancelled, on_chunk
    ):
        raw = json.dumps({
            "reply": self.reply,
            "calls": self.calls,
        })
        on_chunk(raw)
        return raw


def create_assistant(tmp_path, backend=None, catalogue=None):
    store = ConversationService(
        tmp_path / "memory.sqlite3"
    )

    assistant = Conversation(
        config=AIConfig(enabled=True),
        backend=backend or FakeBackend(),
        catalogue={} if catalogue is None else catalogue,
        conversation_service=store,
    )

    discussion = assistant.start_persistent_conversation(
        "Test IA"
    )
    return assistant, store, discussion.id


def test_disabled_by_default(tmp_path):
    assistant, store, conversation_id = create_assistant(
        tmp_path
    )

    assistant.respond("Bonjour")

    assert store.get_messages(conversation_id) == []


def test_normal_exchange_is_saved(tmp_path):
    assistant, store, conversation_id = create_assistant(
        tmp_path
    )

    assistant.set_conversation_persistence(True)
    assistant.respond("Bonjour Jarvis")

    messages = store.get_messages(conversation_id)

    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "Bonjour Jarvis"
    assert messages[1].role == "assistant"
    assert messages[1].content == "Bonjour !"


def test_tool_call_is_not_saved(tmp_path):
    tool = Tool(
        "read_test",
        "Lecture de test",
        object_schema({}),
        lambda: "Information locale",
        "test",
    )

    backend = FakeBackend(
        reply="Information trouvée",
        calls=[{
            "tool": "read_test",
            "arguments": {},
        }],
    )

    assistant, store, conversation_id = create_assistant(
        tmp_path,
        backend=backend,
        catalogue={"read_test": tool},
    )

    assistant.set_conversation_persistence(True)
    assistant.respond("Lis les informations")

    assert store.get_messages(conversation_id) == []


def test_sensitive_exchange_is_not_saved(tmp_path):
    assistant, store, conversation_id = create_assistant(
        tmp_path
    )

    assistant.set_conversation_persistence(True)
    assistant.respond(
        "Confirme action IA abcdef12"
    )

    assert store.get_messages(conversation_id) == []


def test_cancelled_generation_is_not_saved(tmp_path):
    assistant, store, conversation_id = create_assistant(
        tmp_path
    )

    assistant.set_conversation_persistence(True)

    def cancel_on_progress(event):
        if event["kind"] == "progress":
            assistant.stop()

    assistant.listener = cancel_on_progress

    result = assistant.respond("Bonjour")

    assert "annulée" in result.lower()
    assert store.get_messages(conversation_id) == []


def test_disabled_after_activation(tmp_path):
    assistant, store, conversation_id = create_assistant(
        tmp_path
    )

    assistant.set_conversation_persistence(True)
    assistant.respond("Premier message")

    assistant.set_conversation_persistence(False)
    assistant.respond("Deuxième message")

    messages = store.get_messages(conversation_id)

    assert len(messages) == 2
    assert messages[0].content == "Premier message"
