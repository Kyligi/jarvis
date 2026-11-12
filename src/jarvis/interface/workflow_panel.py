"""Interface de supervision des workflows Jarvis V1.7."""

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QObject
from jarvis.context.plans import build_plan, list_plans
from jarvis.context.workflow_runner import WorkflowRunner


class WorkflowPanel(QWidget):
    """Pilote les plans via le CommandBus existant."""

    ACTIVE_STATES = {
        "ready",
        "running",
        "review",
        "cancelling",
    }

    def __init__(self, context, parent=None):
        super().__init__(parent)

        self.context = context

        # Le workflow appartient à la session Jarvis,
        # pas au panneau graphique.
        runner = getattr(
            context,
            "_workflow_runner",
            None,
        )

        if runner is None:
            parent = (
                context
                if isinstance(context, QObject)
                else None
            )

            runner = WorkflowRunner(
                context.commands,
                parent,
            )

            context._workflow_runner = runner

        self.runner = runner

        self.setObjectName("workflowPanel")

        layout = QVBoxLayout(self)

        self.heading = QLabel("WORKFLOWS SUPERVISÉS")
        layout.addWidget(self.heading)

        self.selector = QComboBox()
        self.selector.setAccessibleName(
            "Sélection du workflow"
        )

        for plan in list_plans():
            self.selector.addItem(
                plan.title,
                plan.id,
            )

        layout.addWidget(self.selector)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(165)
        self.preview.setAccessibleName(
            "Prévisualisation du workflow"
        )
        layout.addWidget(self.preview)

        self.status = QLabel("Aucun workflow lancé.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        actions = QHBoxLayout()

        self.start_button = QPushButton("Démarrer")
        self.continue_button = QPushButton("Continuer")
        self.cancel_button = QPushButton("Annuler")

        self.start_button.clicked.connect(
            self.start_selected
        )
        self.continue_button.clicked.connect(
            self.continue_workflow
        )
        self.cancel_button.clicked.connect(
            self.cancel_workflow
        )

        actions.addWidget(self.start_button)
        actions.addWidget(self.continue_button)
        actions.addWidget(self.cancel_button)

        layout.addLayout(actions)

        self.history = QTextEdit()
        self.history.setReadOnly(True)
        self.history.setMinimumHeight(150)
        self.history.setPlaceholderText(
            "Les résultats des étapes apparaîtront ici."
        )
        self.history.setAccessibleName(
            "Résultats du workflow"
        )

        layout.addWidget(self.history)

        self.selector.currentIndexChanged.connect(
            self.show_preview
        )

        self.runner.updated.connect(
            self.update_state
        )
        # Retrouver le plan en cours après
        # la recréation du HUD.
        active_plan_id = self.runner.state.plan_id

        if active_plan_id is not None:
            index = self.selector.findData(
                active_plan_id
            )

            if index >= 0:
                self.selector.setCurrentIndex(index)

        self.show_preview()
        self.update_state(self.runner.state)

    def selected_plan(self):
        plan_id = self.selector.currentData()

        if not plan_id:
            return None

        return build_plan(plan_id)

    def show_preview(self, *args):
        plan = self.selected_plan()

        if plan is None:
            self.preview.clear()
            return

        self.preview.setPlainText(
            plan.preview()
        )

    def start_selected(self):
        plan = self.selected_plan()

        if plan is None:
            return

        answer = QMessageBox.question(
            self,
            "Confirmer le workflow",
            (
                f"{plan.preview()}\n\n"
                "Autoriser Jarvis à démarrer "
                "la première étape ?\n\n"
                "Les étapes suivantes demanderont "
                "une nouvelle confirmation."
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            if self.runner.confirmation_probe():
                QMessageBox.warning(
                    self,
                    "Confirmation en attente",
                    (
                        "Un scénario attend déjà une validation. "
                        "Confirme-le ou annule-le avant de "
                        "démarrer un autre workflow."
                    ),
                )
                return
        except Exception:
            QMessageBox.warning(
                self,
                "État indisponible",
                "Impossible de vérifier les confirmations.",
            )
            return

        try:
            started = self.runner.start(
                plan.id,
                approved=True,
            )
        except (ValueError, RuntimeError) as error:
            QMessageBox.warning(
                self,
                "Workflow indisponible",
                str(error),
            )
            return

        if not started:
            QMessageBox.warning(
                self,
                "Workflow non démarré",
                "Le moteur est occupé ou a refusé la commande.",
            )

    def continue_workflow(self):
        state = self.runner.state

        if state.status != "review":
            return

        plan = self.runner.plan

        if plan is None:
            return

        next_index = state.step_index + 1

        if next_index >= len(plan.steps):
            return

        step = plan.steps[next_index]

        answer = QMessageBox.question(
            self,
            "Continuer le workflow",
            (
                "Résultat de l'étape précédente :\n\n"
                f"{state.last_result}\n\n"
                "Le résultat n'est pas automatiquement "
                "considéré comme une réussite.\n\n"
                f"Étape suivante : {step.title}\n"
                f"Commande : {step.command}\n"
                f"{step.description}\n\n"
                "Autoriser cette nouvelle étape ?"
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        if not self.runner.advance(approved=True):
            QMessageBox.warning(
                self,
                "Étape non lancée",
                "Le moteur n'a pas accepté l'étape suivante.",
            )

    def cancel_workflow(self):
        state = self.runner.state

        if state.status not in self.ACTIVE_STATES:
            return

        answer = QMessageBox.question(
            self,
            "Arrêter le workflow",
            (
                "Arrêter les étapes restantes ?\n\n"
                "Une commande déjà lancée ne sera pas "
                "interrompue brutalement."
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer == QMessageBox.StandardButton.Yes:
            self.runner.cancel()

    def update_state(self, state):
        """Actualise le panneau, sans lancer de commande."""

        labels = {
            "idle": "Aucun workflow lancé.",
            "ready": "Plan prêt.",
            "running": "Commande en cours.",
            "review": "Résultat à vérifier.",
            "cancelling": "Annulation en attente.",
            "cancelled": "Workflow annulé.",
            "blocked": "Workflow bloqué.",
            "completed": "Toutes les étapes sont terminées.",
            "confirmation_required": (
                "Confirmation de scénario requise."
            ),
        }

        self.status.setText(
            f"{labels.get(state.status, state.status)}\n"
            f"{state.message}"
        )

        is_active = state.status in self.ACTIVE_STATES

        self.selector.setEnabled(not is_active)

        confirmation_pending = False

        if state.status == "confirmation_required":
            try:
                confirmation_pending = bool(
                    self.runner.confirmation_probe()
                )
            except Exception:
                confirmation_pending = True

        self.start_button.setEnabled(
            not is_active and not confirmation_pending
        )

        self.continue_button.setEnabled(
            state.status == "review"
        )

        self.cancel_button.setEnabled(
            state.status in {
                "ready",
                "running",
                "review",
            }
        )

        lines = []

        for index, result in enumerate(
            state.history,
            start=1,
        ):
            lines.extend([
                f"ÉTAPE {index} — {result.step_id}",
                f"Commande : {result.command}",
                f"Statut : {result.status.upper()}",
                "Résultat observé :",
                result.response,
                "",
            ])

        if state.status in {"running", "cancelling"}:
            lines.append(
                f"Étape {state.step_index + 1} "
                f"sur {state.step_count} en cours."
            )

        self.history.setPlainText(
            "\n".join(lines)
        )
