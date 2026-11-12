"""Tests des actions contextuelles contrôlées."""

from unittest.mock import Mock

import pytest

from jarvis.context.actions import (
    ALLOWED_ACTIONS,
    resolve_action,
    submit_action,
)
from jarvis.context.suggestions import Suggestion


def suggestion(action_id):
    return Suggestion(
        id="test",
        title="Suggestion de test",
        description="Description",
        action_id=action_id,
    )


def test_known_action():
    action = resolve_action(
        suggestion("suggest_mode_travail")
    )

    assert action is not None
    assert action.command == "mode Travail"


def test_unknown_action():
    assert resolve_action(
        suggestion("unknown_action")
    ) is None


def test_no_arbitrary_command():
    assert "rm -rf /" not in [
        action.command
        for action in ALLOWED_ACTIONS.values()
    ]


def test_action_submitted_through_command_bus():
    bus = Mock()
    bus.submit.return_value = True

    accepted = submit_action(
        suggestion("suggest_mode_travail"),
        bus,
    )

    assert accepted is True
    bus.submit.assert_called_once_with("mode Travail")


def test_rejected_command():
    bus = Mock()
    bus.submit.return_value = False

    assert not submit_action(
        suggestion("suggest_mode_travail"),
        bus,
    )


def test_unknown_action_never_submitted():
    bus = Mock()

    assert not submit_action(
        suggestion("unknown_action"),
        bus,
    )

    bus.submit.assert_not_called()


def test_invalid_suggestion():
    with pytest.raises(TypeError):
        resolve_action("mode Travail")
@pytest.mark.parametrize(
    ("action_id", "expected_command"),
    [
        ("suggest_restore_travail", "mode Travail"),
        ("suggest_restore_gaming", "mode Gaming"),
        ("suggest_restore_etudes", "mode Etudes"),
    ],
)
def test_environment_restore_actions(
    action_id,
    expected_command,
):
    action = resolve_action(
        suggestion(action_id)
    )

    assert action is not None
    assert action.command == expected_command


def test_restore_action_uses_command_bus():
    bus = Mock()
    bus.submit.return_value = True

    accepted = submit_action(
        suggestion("suggest_restore_travail"),
        bus,
    )

    assert accepted
    bus.submit.assert_called_once_with(
        "mode Travail"
    )
