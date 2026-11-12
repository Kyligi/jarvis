"""Tests des suggestions contextuelles Jarvis V1.7."""

import pytest

from jarvis.context.models import ContextSnapshot
from jarvis.context.suggestions import SuggestionEngine


def snapshot(**kwargs):
    return ContextSnapshot(**kwargs)


def test_no_suggestion_without_context():
    engine = SuggestionEngine()
    assert engine.evaluate(snapshot()) == ()


def test_suggest_work_mode():
    engine = SuggestionEngine()

    result = engine.evaluate(snapshot(
        active_project="/home/test/Projects/demo",
        active_mode="etudes",
    ))

    assert len(result) == 1
    assert result[0].id == "development_mode"


def test_no_work_mode_suggestion_if_already_active():
    engine = SuggestionEngine()

    result = engine.evaluate(snapshot(
        active_project="/home/test/Projects/demo",
        active_mode="travail",
    ))

    assert result == ()


def test_suggest_project_selection():
    engine = SuggestionEngine()

    result = engine.evaluate(snapshot(
        active_mode="travail",
    ))

    assert result[0].id == "select_project"


def test_unknown_project_source_is_not_treated_as_absent():
    engine = SuggestionEngine()

    result = engine.evaluate(snapshot(
        active_mode="travail",
        errors=("project",),
    ))

    assert result == ()


def test_high_cpu():
    engine = SuggestionEngine()

    result = engine.evaluate(snapshot(
        cpu_percent=95.0,
    ))

    assert result[0].id == "high_cpu"
    assert result[0].priority == 3


def test_threshold_is_inclusive():
    engine = SuggestionEngine()

    result = engine.evaluate(snapshot(
        cpu_percent=90.0,
        ram_percent=90.0,
        disk_percent=90.0,
    ))

    assert {item.id for item in result} == {
        "high_cpu",
        "high_ram",
        "high_disk",
    }


def test_below_threshold():
    engine = SuggestionEngine()

    result = engine.evaluate(snapshot(
        cpu_percent=89.9,
        ram_percent=89.9,
        disk_percent=89.9,
    ))

    assert result == ()


def test_cooldown_and_expiration():
    current_time = [1000.0]

    engine = SuggestionEngine(
        cooldown_seconds=300,
        clock=lambda: current_time[0],
    )

    context = snapshot(cpu_percent=95)

    assert len(engine.evaluate(context)) == 1
    assert engine.evaluate(context) == ()

    current_time[0] += 299
    assert engine.evaluate(context) == ()

    current_time[0] += 1
    assert len(engine.evaluate(context)) == 1


def test_priority_order():
    engine = SuggestionEngine()

    result = engine.evaluate(snapshot(
        active_mode="travail",
        cpu_percent=95,
        ram_percent=95,
    ))

    assert [item.priority for item in result] == [
        3, 3, 1
    ]


def test_reset_cooldown():
    engine = SuggestionEngine()
    context = snapshot(cpu_percent=95)

    assert engine.evaluate(context)
    assert not engine.evaluate(context)

    engine.reset()

    assert engine.evaluate(context)


def test_invalid_cooldown():
    with pytest.raises(ValueError):
        SuggestionEngine(cooldown_seconds=-1)
