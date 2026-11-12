"""Tests des suggestions de la page Accueil."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox

from jarvis.context.models import ContextSnapshot
from jarvis.interface.pages.home import HomePage


class FakeReader(QObject):
    result = Signal(object)
    failed = Signal(str)
    idle = Signal()

    def __init__(self):
        super().__init__()
        self.stopped = False

    def start(self, callback):
        if self.stopped:
            return False

        try:
            value = callback()
            self.result.emit(value)
        except Exception as error:
            self.failed.emit(type(error).__name__)
        finally:
            self.idle.emit()

        return True

    def shutdown(self):
        self.stopped = True

class FakeMonitor(QObject):
    updated = Signal(object)
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.latest = None


@pytest.fixture
def home_ui(qapp):
    snapshot = ContextSnapshot(
        active_app="foot",
        active_project="/tmp/jarvis",
        active_mode="etudes",
    )
    reader = FakeReader()
    context = SimpleNamespace(
        monitor=FakeMonitor(),
        service=SimpleNamespace(
            home=lambda: {
                "project": None,
                "mode": "etudes",
            }
        ),
        context_service=SimpleNamespace(
            collect=lambda: snapshot
        ),
        commands=SimpleNamespace(
            submit=Mock()
        ),
        reader=lambda: reader,
    )

    page = HomePage(context)

    yield page, context, snapshot

    page.close()
    reader.shutdown()
    page.deleteLater()
    qapp.processEvents()

def test_home_context_loaded(home_ui):
    page, _, snapshot = home_ui

    result = page.load()

    assert result["_context_snapshot"] == snapshot


def test_home_suggestion_display(home_ui):
    page, _, snapshot = home_ui

    page.update_suggestions(snapshot)

    assert "development_mode" in page.visible_suggestions
    assert page.suggestions_layout.count() == 1


def test_home_suggestion_ignored(home_ui):
    page, _, snapshot = home_ui

    page.update_suggestions(snapshot)
    page.ignore_suggestion("development_mode")

    assert page.visible_suggestions == {}
    assert "development_mode" in page.ignored_suggestions


def test_home_ignored_suggestion_stays_hidden(home_ui):
    page, _, snapshot = home_ui

    page.update_suggestions(snapshot)
    page.ignore_suggestion("development_mode")
    page.update_suggestions(snapshot)

    assert page.visible_suggestions == {}


def test_home_preview_never_executes(
    home_ui,
    monkeypatch,
):
    page, context, snapshot = home_ui

    page.update_suggestions(snapshot)
    suggestion = page.visible_suggestions[
        "development_mode"
    ]

    messages = []

    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args: messages.append(args),
    )

    page.preview_suggestion(suggestion)

    assert len(messages) == 1
    context.commands.submit.assert_not_called()


def test_execute_cancelled(home_ui, monkeypatch):
    page, context, snapshot = home_ui

    page.update_suggestions(snapshot)
    suggestion = page.visible_suggestions[
        "development_mode"
    ]

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.No,
    )

    page.execute_suggestion(suggestion)

    context.commands.submit.assert_not_called()


def test_execute_confirmed(home_ui, monkeypatch):
    page, context, snapshot = home_ui

    page.update_suggestions(snapshot)
    suggestion = page.visible_suggestions[
        "development_mode"
    ]

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )

    context.commands.submit.return_value = True

    page.execute_suggestion(suggestion)

    context.commands.submit.assert_called_once_with(
        "mode Travail"
    )

    assert "development_mode" in page.ignored_suggestions


def test_execute_unknown_action(home_ui, monkeypatch):
    from jarvis.context.suggestions import Suggestion

    page, context, _ = home_ui

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: None,
    )

    unknown = Suggestion(
        id="unknown",
        title="Action inconnue",
        description="Test",
        action_id="not_allowed",
    )

    page.execute_suggestion(unknown)

    context.commands.submit.assert_not_called()


def test_restore_suggestion_visible(home_ui):
    from jarvis.context.suggestions import Suggestion

    page, _, snapshot = home_ui

    restore = Suggestion(
        id="restore_environment_etudes",
        title="Restaurer Études",
        description="Notion manquant",
        action_id="suggest_restore_etudes",
        priority=70,
    )

    page.update_suggestions(
        snapshot,
        restore_suggestions=(restore,),
    )

    assert restore.id in page.visible_suggestions


def test_restore_disappears_when_complete(home_ui):
    from jarvis.context.suggestions import Suggestion

    page, _, snapshot = home_ui

    restore = Suggestion(
        id="restore_environment_etudes",
        title="Restaurer Études",
        description="Notion manquant",
        action_id="suggest_restore_etudes",
        priority=70,
    )

    page.update_suggestions(
        snapshot,
        restore_suggestions=(restore,),
    )

    page.update_suggestions(
        snapshot,
        restore_suggestions=(),
    )

    assert restore.id not in page.visible_suggestions


def test_ignored_restore_stays_hidden(home_ui):
    from jarvis.context.suggestions import Suggestion

    page, _, snapshot = home_ui

    restore = Suggestion(
        id="restore_environment_etudes",
        title="Restaurer Études",
        description="Notion manquant",
        action_id="suggest_restore_etudes",
        priority=70,
    )

    page.update_suggestions(
        snapshot,
        restore_suggestions=(restore,),
    )

    page.ignore_suggestion(restore.id)

    page.update_suggestions(
        snapshot,
        restore_suggestions=(restore,),
    )

    assert restore.id not in page.visible_suggestions


def test_restore_returns_after_problem_reappears(home_ui):
    from jarvis.context.suggestions import Suggestion

    page, _, snapshot = home_ui

    restore = Suggestion(
        id="restore_environment_etudes",
        title="Restaurer Études",
        description="Notion manquant",
        action_id="suggest_restore_etudes",
        priority=70,
    )

    page.update_suggestions(
        snapshot,
        restore_suggestions=(restore,),
    )

    page.ignore_suggestion(restore.id)

    # L'environnement redevient complet.
    page.update_suggestions(
        snapshot,
        restore_suggestions=(),
    )

    # Puis Notion est à nouveau fermé.
    page.update_suggestions(
        snapshot,
        restore_suggestions=(restore,),
    )

    assert restore.id in page.visible_suggestions


def test_identical_suggestions_keep_same_widget(home_ui):
    """Un rafraîchissement identique conserve la carte Qt."""

    page, _, snapshot = home_ui

    page.update_suggestions(snapshot)

    assert page.suggestions_layout.count() > 0

    first_widget = (
        page.suggestions_layout.itemAt(0).widget()
    )

    page.update_suggestions(snapshot)

    second_widget = (
        page.suggestions_layout.itemAt(0).widget()
    )

    assert first_widget is second_widget


def test_render_without_changes_keeps_widget(home_ui):
    """Un rendu manuel identique ne détruit rien."""

    page, _, snapshot = home_ui

    page.update_suggestions(snapshot)

    assert page.suggestions_layout.count() > 0

    first_widget = (
        page.suggestions_layout.itemAt(0).widget()
    )

    page.render_suggestions()
    page.render_suggestions()

    assert (
        page.suggestions_layout.itemAt(0).widget()
        is first_widget
    )


def test_ignoring_suggestion_updates_ui(home_ui):
    """Ignorer une suggestion met le panneau à jour."""

    page, _, snapshot = home_ui

    page.update_suggestions(snapshot)

    assert page.suggestions_layout.count() > 0

    suggestion_id = next(
        iter(page.visible_suggestions)
    )

    initial_count = page.suggestions_layout.count()

    page.ignore_suggestion(suggestion_id)

    assert suggestion_id not in page.visible_suggestions
    assert (
        page.suggestions_layout.count()
        == initial_count - 1
    )


def test_description_change_updates_widget(home_ui):
    """Un changement de contenu reconstruit la carte."""

    from dataclasses import replace

    page, _, snapshot = home_ui

    page.update_suggestions(snapshot)

    assert page.suggestions_layout.count() > 0

    suggestion_id = next(
        iter(page.visible_suggestions)
    )

    original = page.visible_suggestions[suggestion_id]

    updated = replace(
        original,
        description="Nouvelle description de test",
    )

    page.visible_suggestions[suggestion_id] = updated

    page.render_suggestions()

    assert page._rendered_suggestions_signature is not None

    assert any(
        "Nouvelle description de test" in str(item)
        for row in page._rendered_suggestions_signature
        for item in row
    )


def test_repeated_identical_refreshes_keep_widgets(home_ui):
    """100 rendus identiques ne recréent pas les cartes."""

    page, _, snapshot = home_ui

    page.update_suggestions(snapshot)

    count = page.suggestions_layout.count()
    assert count > 0

    original_widgets = [
        page.suggestions_layout.itemAt(index).widget()
        for index in range(count)
    ]

    for _ in range(100):
        page.update_suggestions(snapshot)

    assert page.suggestions_layout.count() == count

    for index, original in enumerate(original_widgets):
        assert (
            page.suggestions_layout.itemAt(index).widget()
            is original
        )


def test_repeated_suggestion_changes_do_not_accumulate(home_ui):
    """Les cartes affichées correspondent aux suggestions actives."""

    from jarvis.context.suggestions import Suggestion

    page, _, snapshot = home_ui

    restore = Suggestion(
        id="restore_environment_etudes",
        title="Restaurer Études",
        description="Notion manquant",
        action_id="suggest_restore_etudes",
        priority=70,
    )

    for _ in range(30):
        page.update_suggestions(
            snapshot,
            restore_suggestions=(restore,),
        )

        assert (
            page.suggestions_layout.count()
            == len(page.visible_suggestions)
        )

        page.update_suggestions(
            snapshot,
            restore_suggestions=(),
        )

        assert (
            page.suggestions_layout.count()
            == len(page.visible_suggestions)
        )


def test_deferred_widget_deletion_is_safe(home_ui):
    """Qt peut traiter les destructions différées des cartes."""

    from PySide6.QtCore import QCoreApplication, QEvent
    from jarvis.context.suggestions import Suggestion
    import shiboken6

    page, _, snapshot = home_ui

    restore = Suggestion(
        id="restore_environment_etudes",
        title="Restaurer Études",
        description="Notion manquant",
        action_id="suggest_restore_etudes",
        priority=70,
    )

    page.update_suggestions(
        snapshot,
        restore_suggestions=(restore,),
    )

    # Forcer plusieurs reconstructions.
    for index in range(20):
        updated = Suggestion(
            id=restore.id,
            title=restore.title,
            description=f"Modification {index}",
            action_id=restore.action_id,
            priority=restore.priority,
        )

        page.update_suggestions(
            snapshot,
            restore_suggestions=(updated,),
        )

    page.update_suggestions(
        snapshot,
        restore_suggestions=(),
    )

    # Vider la file de destructions Qt.
    QCoreApplication.sendPostedEvents(
        None,
        QEvent.Type.DeferredDelete,
    )

    assert (
        page.suggestions_layout.count()
        == len(page.visible_suggestions)
    )

    for index in range(
        page.suggestions_layout.count()
    ):
        widget = (
            page.suggestions_layout.itemAt(index).widget()
        )

        assert widget is not None
        assert shiboken6.isValid(widget)
