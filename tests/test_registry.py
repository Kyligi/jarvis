import sqlite3
from dataclasses import replace
from unittest.mock import Mock

import pytest

from jarvis import registry
from jarvis.core.commands import execute


@pytest.mark.parametrize("entry", registry.COMMANDS, ids=lambda e: e.id)
def test_every_example_and_alias_resolves(entry):
    for text in (*entry.examples, *entry.aliases):
        for value in (text, "Jarvis, " + text.upper(), "Jarvis : " + text):
            resolved = registry.resolve(value)
            assert resolved is not None, value
            assert resolved.command.id == entry.id, value


@pytest.mark.parametrize("entry", registry.COMMANDS, ids=lambda e: e.id)
def test_every_command_dispatches_and_is_documented(entry, monkeypatch):
    handler = Mock(return_value="OK")
    replacement = replace(entry, handler=handler)
    monkeypatch.setattr(registry, "COMMANDS", (replacement,))
    assert registry.dispatch(entry.examples[0]) == "OK"
    assert handler.call_count == 1
    assert registry.help_text().count("• " + entry.name + "\n") == 1


@pytest.mark.parametrize(("text", "identifier", "arguments"), [
    ("Jarvis : objectif projet : Préserver ABC : clé", "projects.objective", ("Préserver ABC : clé",)),
    ("Jarvis, suis le fichier Dossier École/Main.py", "sessions.track", ("Dossier École/Main.py",)),
    ("OUVRE PROJET ProjetÉcole", "projects.open", ("ProjetÉcole",)),
    ("objectif projet : ouvre un terminal", "projects.objective", ("ouvre un terminal",)),
    ("suis le fichier reprends rust.txt", "sessions.track", ("reprends rust.txt",)),
    ("Jarvis, change vers espace 9", "desktop.workspace", ("9",)),
    ("Jarvis, peux-tu ouvrir le terminal", "desktop.terminal", ()),
    ("reprendre ce projet rust", "projects.rust.resume", ()),
])
def test_dynamic_parameters(text, identifier, arguments):
    resolved = registry.resolve(text)
    assert resolved.command.id == identifier
    assert resolved.arguments == arguments


def test_unique_registry_and_help():
    registry.validate_registry()
    assert len({c.id for c in registry.COMMANDS}) == len(registry.COMMANDS)
    assert registry.help_text().count("• ") == len(registry.COMMANDS)
    first = registry.COMMANDS[0]
    with pytest.raises(ValueError):
        registry.validate_registry((first, first))
    with pytest.raises(ValueError):
        registry.validate_registry((first, replace(first, id="collision")))


@pytest.mark.parametrize("text", ["", "rm -rf /", "git reset --hard", "exécute bash", "workspace 10", "passe au workspace 10"])
def test_no_arbitrary_command(text):
    assert registry.resolve(text) is None
    assert execute(text) in {"Écris une commande.", "Commande inconnue. Tape 'aide'."}


def test_handler_failure_does_not_log_secrets(monkeypatch, caplog):
    entry = replace(registry.COMMANDS[0], handler=Mock(side_effect=RuntimeError("secret-token")))
    monkeypatch.setattr(registry, "COMMANDS", (entry,))
    assert "RuntimeError" in execute("aide")
    assert "secret-token" not in caplog.text
    assert "command_failed" in caplog.text


def test_history_failure_is_visible(monkeypatch):
    monkeypatch.setattr("jarvis.core.commands.remember", Mock(side_effect=sqlite3.OperationalError("locked")))
    assert "historique non enregistré" in execute("aide")


def test_history_records_only_identifier(project):
    from jarvis.memory.database import DB
    from jarvis.persistence.sqlite import connect
    assert "enregistré" in execute("objectif projet : secret-token")
    with connect(DB) as db:
        assert db.execute("SELECT command, result FROM history").fetchall() == [("projects.objective", "ok")]


def test_compatibility_entrypoints(monkeypatch):
    from jarvis.commands import handle_system_command
    from jarvis.modes.commands import handle_mode_command
    from jarvis.projects.commands import handle_session_command
    from jarvis.projects.manager import handle_project_command
    monkeypatch.setattr(registry, "COMMANDS", tuple(replace(c, handler=lambda *a: "ok") for c in registry.COMMANDS))
    assert handle_system_command("ouvre un terminal") == "ok"
    assert handle_session_command("ma session") == "ok"
    assert handle_project_command("mes projets") == "ok"
    assert handle_mode_command("mode Études") == "ok"
