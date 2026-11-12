"""Tests des résultats d'exécution structurés."""

from dataclasses import FrozenInstanceError

import pytest

from jarvis.context.command_outcomes import (
    CommandOutcome,
    classify_outcome,
)


def test_structured_success():
    assert classify_outcome(
        {"state": "success"}
    ) == "success"


def test_structured_failure():
    assert classify_outcome(
        {"state": "failed"}
    ) == "failed"


def test_structured_cancellation():
    assert classify_outcome(
        {"state": "cancelled"}
    ) == "failed"


def test_worker_failure():
    assert classify_outcome(
        "Commande terminée",
        failed=True,
    ) == "failed"


def test_pending_confirmation():
    assert classify_outcome(
        "Prévisualisation du scénario",
        confirmation_required=True,
    ) == "confirmation_required"


def test_free_text_is_not_proof():
    assert classify_outcome(
        "Mode Travail activé"
    ) == "unknown"


def test_scenario_error():
    assert classify_outcome(
        {"scenario_error": "Opération refusée"}
    ) == "failed"


def test_outcome_immutable():
    outcome = CommandOutcome(
        execution_id="abc",
        command_id="modes.travail",
        status="unknown",
        response="Mode Travail activé",
    )

    assert not outcome.verified_success

    with pytest.raises(FrozenInstanceError):
        outcome.status = "success"
