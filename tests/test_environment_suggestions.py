"""Tests des suggestions de restauration Jarvis."""

import pytest

from jarvis.context.environment import EnvironmentReport
from jarvis.context.environment_suggestions import (
    suggest_environment_restore,
)


def report(mode, status, missing=()):
    return EnvironmentReport(
        mode=mode,
        status=status,
        missing=missing,
    )


def test_travail_missing_terminal():
    suggestions = suggest_environment_restore(
        "travail",
        report=report(
            "travail",
            "incomplete",
            ("Foot",),
        ),
        customized=False,
    )

    assert len(suggestions) == 1

    suggestion = suggestions[0]

    assert "Foot" in suggestion.description
    assert suggestion.action_id == (
        "suggest_restore_travail"
    )


def test_travail_missing_multiple_apps():
    suggestions = suggest_environment_restore(
        "travail",
        report=report(
            "travail",
            "incomplete",
            ("Éditeur", "Foot"),
        ),
        customized=False,
    )

    assert len(suggestions) == 1
    assert "Éditeur" in suggestions[0].description
    assert "Foot" in suggestions[0].description


def test_gaming_missing_steam():
    suggestions = suggest_environment_restore(
        "gaming",
        report=report(
            "gaming",
            "incomplete",
            ("Steam",),
        ),
        customized=False,
    )

    assert len(suggestions) == 1
    assert suggestions[0].action_id == (
        "suggest_restore_gaming"
    )


def test_etudes_missing_notion():
    suggestions = suggest_environment_restore(
        "etudes",
        report=report(
            "etudes",
            "incomplete",
            ("Notion",),
        ),
        customized=False,
    )

    assert len(suggestions) == 1
    assert "Notion" in suggestions[0].description


@pytest.mark.parametrize(
    "mode",
    ["travail", "gaming", "etudes"],
)
def test_complete_environment_has_no_suggestion(mode):
    result = suggest_environment_restore(
        mode,
        report=report(mode, "complete"),
        customized=False,
    )

    assert result == ()


def test_unknown_inventory_has_no_suggestion():
    result = suggest_environment_restore(
        "travail",
        report=report("travail", "unknown"),
        customized=False,
    )

    assert result == ()


def test_custom_profile_has_no_suggestion():
    result = suggest_environment_restore(
        "travail",
        report=report(
            "travail",
            "incomplete",
            ("Foot",),
        ),
        customized=True,
    )

    assert result == ()


def test_unknown_profile_configuration_is_safe(
    monkeypatch,
):
    from jarvis.context import environment_suggestions

    monkeypatch.setattr(
        environment_suggestions,
        "is_custom_profile",
        lambda mode: None,
    )

    result = suggest_environment_restore(
        "travail",
        report=report(
            "travail",
            "incomplete",
            ("Foot",),
        ),
    )

    assert result == ()


def test_wrong_mode_report_rejected():
    result = suggest_environment_restore(
        "travail",
        report=report(
            "gaming",
            "incomplete",
            ("Steam",),
        ),
        customized=False,
    )

    assert result == ()


def test_unknown_mode():
    result = suggest_environment_restore(
        "unknown",
        customized=False,
    )

    assert result == ()


def test_incomplete_without_missing_apps():
    result = suggest_environment_restore(
        "travail",
        report=report("travail", "incomplete"),
        customized=False,
    )

    assert result == ()
