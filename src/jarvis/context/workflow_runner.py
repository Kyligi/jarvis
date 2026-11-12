"""Exécution supervisée des workflows Jarvis V1.7."""

from dataclasses import dataclass, replace

from PySide6.QtCore import QObject, Signal

from jarvis.context.plans import build_plan


@dataclass(frozen=True)
class StepResult:
    """Résultat observé d'une étape."""

    step_id: str
    command: str
    response: str
    status: str = "unknown"


@dataclass(frozen=True)
class WorkflowState:
    """État public d'un workflow."""

    status: str = "idle"
    plan_id: str | None = None
    step_index: int = 0
    step_count: int = 0
    last_result: str = ""
    history: tuple[StepResult, ...] = ()
    message: str = ""


class WorkflowRunner(QObject):
    """Supervise des commandes du CommandBus existant."""

    updated = Signal(object)

    TERMINAL = {
        "idle",
        "completed",
        "cancelled",
        "blocked",
        "confirmation_required",
    }

    def __init__(
        self,
        command_bus,
        parent=None,
        confirmation_probe=None,
    ):
        super().__init__(parent)

        self.bus = command_bus
        self.plan = None
        self.state = WorkflowState()

        if confirmation_probe is None:
            from jarvis.scenarios.engine import engine
            confirmation_probe = engine.confirmation_pending

        self.confirmation_probe = confirmation_probe

        self._response = None
        self._cancel_requested = False
        self._execution_id = None
        self._dispatching = False
        self._shutting_down = False

        # CommandBus V1.7 : résultats structurés.
        self._typed_results = hasattr(
            self.bus,
            "execution_finished",
        )

        if self._typed_results:
            if hasattr(self.bus, "execution_reserved"):
                self.bus.execution_reserved.connect(
                    self._capture_execution
                )
            self.bus.execution_finished.connect(
                self._on_execution_finished
            )
        else:
            # Compatibilité avec les anciens FakeBus
            # des tests déjà présents dans le projet.
            self.bus.result.connect(self._on_result)
            self.bus.completed.connect(self._on_completed)

    def _set_state(self, **changes):
        self.state = replace(self.state, **changes)
        self.updated.emit(self.state)

    def start(self, plan_id: str, *, approved=False) -> bool:
        """Démarre uniquement un plan approuvé."""
        if self._shutting_down:
            return False

        if not approved:
            return False

        if self.state.status not in self.TERMINAL:
            return False

        if getattr(self.bus, "busy", False):
            return False

        plan = build_plan(plan_id)

        self.plan = plan
        self._response = None
        self._cancel_requested = False
        self._execution_id = None

        self.state = WorkflowState(
            status="ready",
            plan_id=plan.id,
            step_index=0,
            step_count=len(plan.steps),
            message="Plan approuvé.",
        )
        self.updated.emit(self.state)

        return self._dispatch()

    def _capture_execution(self, execution_id):
        """Capture uniquement notre réservation active."""

        if not self._dispatching:
            return

        if self.state.status != "running":
            return

        self._execution_id = execution_id

    def _dispatch(self) -> bool:
        """Lance une seule étape autorisée."""
        if self._shutting_down:
            return False

        if self.plan is None:
            return False

        index = self.state.step_index

        if not 0 <= index < len(self.plan.steps):
            return False

        if getattr(self.bus, "busy", False):
            self._set_state(
                status="blocked",
                message="CommandBus est occupé.",
            )
            return False

        step = self.plan.steps[index]

        self._response = None
        self._execution_id = None

        self._set_state(
            status="running",
            last_result="",
            message=(
                f"Étape {index + 1} en cours : "
                f"{step.title}"
            ),
        )

        self._dispatching = True

        try:
            accepted = bool(
                self.bus.submit(step.command)
            )
        except Exception as error:
            self._set_state(
                status="blocked",
                message=(
                    "Commande non démarrée : "
                    f"{type(error).__name__}"
                ),
            )
            return False
        finally:
            self._dispatching = False

        if not accepted:
            if self.state.status == "running":
                self._set_state(
                    status="blocked",
                    message=(
                        "Commande refusée par CommandBus."
                    ),
                )
            return False

        # Une implémentation synchrone peut avoir
        # déjà délivré son résultat.
        if self.state.status != "running":
            return accepted

        if self._typed_results:
            execution_id = getattr(
                self.bus,
                "current_execution_id",
                None,
            )

            if not execution_id:
                self._set_state(
                    status="blocked",
                    message=(
                        "Aucun identifiant d'exécution. "
                        "Workflow arrêté par sécurité."
                    ),
                )
                return False

            if self._execution_id is None:
                self._execution_id = execution_id
            elif self._execution_id != execution_id:
                self._set_state(
                    status="blocked",
                    message=(
                        "Identifiants d'exécution "
                        "incohérents."
                    ),
                )
                return False
        return True

    def _on_execution_finished(self, outcome):
        """Ignore tout résultat d'une autre exécution."""
        if (
            self._shutting_down
            and self.state.status != "cancelling"
        ):
            return

        if self.state.status not in {
            "running",
            "cancelling",
        }:
            return

        if self._execution_id is None:
            return

        if getattr(outcome, "execution_id", None) != (
            self._execution_id
        ):
            return

        status = getattr(
            outcome,
            "status",
            "unknown",
        )

        if status not in {
            "success",
            "failed",
            "confirmation_required",
            "unknown",
        }:
            status = "unknown"

        response = getattr(
            outcome,
            "response",
            None,
        )

        self._finish_step(
            response=(
                str(response)
                if response is not None
                else "Aucun résultat transmis."
            ),
            status=status,
        )

    def _on_result(self, value):
        """Compatibilité avec les bus non typés."""
        if (
            self._shutting_down
            and self.state.status != "cancelling"
        ):
            return

        if self.state.status not in {
            "running",
            "cancelling",
        }:
            return

        self._response = str(value)

    def _on_completed(self):
        """Compatibilité avec les anciens tests FakeBus."""
        if (
            self._shutting_down
            and self.state.status != "cancelling"
        ):
            return

        if self._typed_results:
            return

        if self.state.status not in {
            "running",
            "cancelling",
        }:
            return

        response = (
            self._response
            if self._response is not None
            else "Aucun résultat transmis."
        )

        status = "unknown"

        if (
            self.plan is not None
            and self.plan.steps[
                self.state.step_index
            ].command.lower().startswith("mode ")
            and not self._cancel_requested
        ):
            try:
                if self.confirmation_probe():
                    status = "confirmation_required"
            except Exception:
                status = "failed"

        self._finish_step(
            response=response,
            status=status,
        )

    def _finish_step(self, *, response, status):
        """Finalise uniquement l'étape active."""

        if self.plan is None:
            return

        if self.state.status not in {
            "running",
            "cancelling",
        }:
            return

        step = self.plan.steps[
            self.state.step_index
        ]

        record = StepResult(
            step_id=step.id,
            command=step.command,
            response=response,
            status=status,
        )

        history = (
            *self.state.history,
            record,
        )

        self._execution_id = None

        if self._cancel_requested:
            self._set_state(
                status="cancelled",
                history=history,
                last_result=response,
                message=(
                    "Workflow arrêté après la fin "
                    "de la commande active."
                ),
            )
            return

        if status == "failed":
            self._set_state(
                status="blocked",
                history=history,
                last_result=response,
                message=(
                    "Échec de l'étape. "
                    "Les étapes suivantes sont bloquées."
                ),
            )
            return

        if status == "confirmation_required":
            self._set_state(
                status="confirmation_required",
                history=history,
                last_result=response,
                message=(
                    "Une confirmation de scénario est "
                    "nécessaire. Traite-la dans Jarvis "
                    "avant de relancer un workflow."
                ),
            )
            return

        if self.state.step_index + 1 == len(
            self.plan.steps
        ):
            self._set_state(
                status="completed",
                history=history,
                last_result=response,
                message=(
                    "Toutes les étapes sont terminées. "
                    "Vérifie leurs résultats."
                ),
            )
            return

        self._set_state(
            status="review",
            history=history,
            last_result=response,
            message=(
                "Résultat à vérifier avant "
                "l'étape suivante."
                if status == "unknown"
                else "Étape terminée. Confirme la suite."
            ),
        )

    def advance(self, *, approved=False) -> bool:
        """Continue seulement après accord explicite."""
        if self._shutting_down:
            return False

        if not approved:
            return False

        if self.state.status != "review":
            return False

        self._set_state(
            status="ready",
            step_index=self.state.step_index + 1,
            message="Étape suivante approuvée.",
        )

        return self._dispatch()

    def cancel(self) -> bool:
        """Annule sans interrompre le worker Qt."""

        if self.state.status in self.TERMINAL:
            return False

        if self.state.status in {
            "running",
            "cancelling",
        }:
            self._cancel_requested = True

            self._set_state(
                status="cancelling",
                message=(
                    "Annulation demandée. "
                    "Fin de la commande active attendue."
                ),
            )
            return True

        self._set_state(
            status="cancelled",
            message="Workflow annulé.",
        )
        return True
    def shutdown(self) -> None:
        """Prépare l'arrêt sans interrompre CommandBus.

        Cette méthode n'attend aucun thread. L'arrêt
        effectif des workers appartient à AppContext.
        """

        if self._shutting_down:
            return

        self._shutting_down = True

        if self.state.status in {
            "running",
            "cancelling",
        }:
            self._cancel_requested = True

            self._set_state(
                status="cancelling",
                message=(
                    "Fermeture de Jarvis demandée. "
                    "Fin de la commande active attendue."
                ),
            )

        elif self.state.status in {
            "ready",
            "review",
        }:
            self._set_state(
                status="cancelled",
                message=(
                    "Workflow arrêté lors de "
                    "la fermeture de Jarvis."
                ),
            )

