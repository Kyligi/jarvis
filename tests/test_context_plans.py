"""Tests du planificateur Jarvis V1.7."""

from dataclasses import FrozenInstanceError, replace

import pytest

from jarvis.context.plans import (
    ALLOWED_STEPS,
    PLAN_DEFINITIONS,
    ActionPlan,
    build_plan,
    list_plans,
)


def test_prepare_work_plan():
    plan = build_plan("prepare_work")

    assert isinstance(plan, ActionPlan)
    assert len(plan.steps) == 2
    assert plan.steps[0].command == "mode Travail"
    assert plan.steps[1].command == "diagnostic"


def test_save_and_check_plan():
    plan = build_plan("save_and_check")

    assert [step.id for step in plan.steps] == [
        "save_session",
        "diagnostic",
    ]


def test_unknown_plan_rejected():
    with pytest.raises(ValueError):
        build_plan("unknown")


def test_invalid_identifier_rejected():
    with pytest.raises(ValueError):
        build_plan(None)


def test_list_plans():
    plans = list_plans()

    assert len(plans) == 2
    assert {plan.id for plan in plans} == {
        "prepare_work",
        "save_and_check",
    }


def test_preview_does_not_execute():
    plan = build_plan("prepare_work")

    result = plan.preview()

    assert "mode Travail" in result
    assert "diagnostic" in result
    assert "Aucune action n'a été exécutée" in result


def test_plan_is_immutable():
    plan = build_plan("prepare_work")

    with pytest.raises(FrozenInstanceError):
        plan.title = "Nouveau titre"


def test_unknown_step_rejected(monkeypatch):
    monkeypatch.setitem(
        PLAN_DEFINITIONS,
        "invalid",
        ("Invalide", "Test", ("unknown_step",)),
    )

    with pytest.raises(ValueError):
        build_plan("invalid")


def test_too_many_steps_rejected(monkeypatch):
    monkeypatch.setitem(
        PLAN_DEFINITIONS,
        "too_long",
        ("Trop long", "Test", ("diagnostic",) * 6),
    )

    with pytest.raises(ValueError):
        build_plan("too_long")


def test_duplicate_steps_rejected(monkeypatch):
    monkeypatch.setitem(
        PLAN_DEFINITIONS,
        "duplicate",
        ("Doublons", "Test", ("diagnostic", "diagnostic")),
    )

    with pytest.raises(ValueError):
        build_plan("duplicate")


def test_confirmation_metadata():
    plan = build_plan("prepare_work")

    assert plan.steps[0].requires_confirmation
    assert not plan.steps[1].requires_confirmation


def test_only_known_commands():
    commands = {
        step.command for step in ALLOWED_STEPS.values()
    }

    assert commands == {
        "mode Travail",
        "diagnostic",
        "sauvegarde ma session",
    }
