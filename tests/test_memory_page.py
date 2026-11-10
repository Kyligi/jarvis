
"""Tests de la page HUD Mémoire de Jarvis."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QInputDialog, QMessageBox

from jarvis.interface.pages.memory import MemoryPage
from jarvis.memory.service import MemoryService


class FakeReader(QObject):
    """Lecteur minimal pour tester DataPage sans thread."""

    result = Signal(object)
    failed = Signal(str)
    idle = Signal()

    def start(self, callback):
        try:
            self.result.emit(callback())
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.idle.emit()


class FakeContext:
    """Contexte isolé de la véritable application."""

    def __init__(self, service):
        self.conversation = Mock()
        self.commands = SimpleNamespace(
            memory_service=service,
            conversation=self.conversation,
        )

    def reader(self):
        return FakeReader()


@pytest.fixture
def memory_ui(qapp, tmp_path, monkeypatch):
    """Page Mémoire et SQLite temporaire."""

    service = MemoryService(
        db_path=tmp_path / "test_memories.db"
    )

    context = FakeContext(service)
    page = MemoryPage(context)

    messages = {
        "warnings": [],
        "informations": [],
    }

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: messages["warnings"].append(args),
    )

    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args: messages["informations"].append(args),
    )

    yield page, service, context.conversation, messages

    page.close()


def create_selected_memory(page, service):
    """Crée un souvenir et sélectionne sa ligne."""

    memory = service.add_memory(
        "Souvenir temporaire de test",
        category="projects",
        source="explicit",
    )

    page.render(service.list_memories())
    page.table.selectRow(0)

    return memory


def test_memory_page_initialization(memory_ui):
    page, service, _, _ = memory_ui

    assert page.table.columnCount() == 3
    assert page.search_timer.interval() == 250
    assert page.delete_button.isEnabled() is False


def test_memory_page_display(memory_ui):
    page, service, _, _ = memory_ui

    memory = service.add_memory(
        "Je préfère Rust",
        category="preferences",
    )

    page.render(service.list_memories())

    assert page.table.rowCount() == 1
    assert page.table.item(0, 0).text() == str(memory.id)
    assert page.table.item(0, 1).text() == "preferences"
    assert page.table.item(0, 2).text() == "Je préfère Rust"


def test_memory_page_search_limit(memory_ui, monkeypatch):
    page, service, _, _ = memory_ui

    search = Mock(return_value=[])

    monkeypatch.setattr(
        service,
        "search_memories",
        search,
    )

    page.query = "Rust"

    assert page.load() == []

    search.assert_called_once_with(
        "Rust",
        limit=50,
    )


def test_memory_page_category_filter(memory_ui):
    page, service, _, _ = memory_ui

    service.add_memory(
        "Projet Rust",
        category="projects",
    )
    service.add_memory(
        "Préférence Python",
        category="preferences",
    )

    page.render(service.list_memories())

    index = page.category_filter.findData("projects")
    page.category_filter.setCurrentIndex(index)

    visible = [
        row
        for row in range(page.table.rowCount())
        if not page.table.isRowHidden(row)
    ]

    assert len(visible) == 1
    assert page.table.item(
        visible[0], 1
    ).text() == "projects"


def test_memory_page_add(memory_ui):
    page, service, _, _ = memory_ui

    page.new_content.setPlainText(
        "J'apprends à développer Jarvis"
    )

    index = page.new_category.findData("projects")
    page.new_category.setCurrentIndex(index)

    page.add_memory()

    memories = service.list_memories()

    assert len(memories) == 1
    assert memories[0].category == "projects"
    assert memories[0].content == (
        "J'apprends à développer Jarvis"
    )
    assert page.new_content.toPlainText() == ""


def test_delete_without_selection(memory_ui):
    page, service, conversation, _ = memory_ui

    page.delete_selected_memory()

    conversation.request_delete_memory.assert_not_called()
    assert service.list_memories() == []


def test_delete_cancelled(memory_ui, monkeypatch):
    page, service, conversation, _ = memory_ui

    memory = create_selected_memory(page, service)

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.No,
    )

    page.delete_selected_memory()

    conversation.request_delete_memory.assert_not_called()

    assert any(
        item.id == memory.id
        for item in service.list_memories()
    )


def test_delete_wrong_code(memory_ui, monkeypatch):
    page, service, conversation, messages = memory_ui

    memory = create_selected_memory(page, service)

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )

    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *args: ("mauvais-code", True),
    )

    conversation.request_delete_memory.return_value = (
        "Code de confirmation requis"
    )

    conversation.confirm_delete_memory.side_effect = (
        ValueError("Code invalide")
    )

    page.delete_selected_memory()

    conversation.request_delete_memory.assert_called_once_with(
        memory.id
    )

    conversation.confirm_delete_memory.assert_called_once_with(
        "mauvais-code"
    )

    assert any(
        item.id == memory.id
        for item in service.list_memories()
    )

    assert len(messages["warnings"]) == 1


def test_delete_correct_code(memory_ui, monkeypatch):
    page, service, conversation, messages = memory_ui

    memory = create_selected_memory(page, service)

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )

    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *args: ("1234abcd", True),
    )

    conversation.request_delete_memory.return_value = (
        "Code de confirmation : 1234abcd"
    )

    def confirm(code):
        assert code == "1234abcd"
        service.delete_memory(memory.id)
        return "Souvenir supprimé"

    conversation.confirm_delete_memory.side_effect = confirm

    page.delete_selected_memory()

    assert not any(
        item.id == memory.id
        for item in service.list_memories()
    )

    assert len(messages["informations"]) == 1
    assert not messages["warnings"]


def test_delete_confirmation_dialog_cancelled(
    memory_ui,
    monkeypatch,
):
    page, service, conversation, _ = memory_ui

    memory = create_selected_memory(page, service)

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )

    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *args: ("", False),
    )

    conversation.request_delete_memory.return_value = (
        "Confirmation requise"
    )

    page.delete_selected_memory()

    conversation.confirm_delete_memory.assert_not_called()

    assert any(
        item.id == memory.id
        for item in service.list_memories()
    )
