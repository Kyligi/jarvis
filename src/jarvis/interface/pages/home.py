"""Accueil du HUD Jarvis : monitoring et suggestions contextuelles."""

import time

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from jarvis.context.suggestions import SuggestionEngine
from jarvis.interface.components import Card, label, text_view
from jarvis.interface.dashboard import Metric
from jarvis.interface.pages.base import DataPage
from jarvis.context.actions import resolve_action, submit_action
from jarvis.context.environment_suggestions import (
    suggest_environment_restore,
)

class HomePage(DataPage):
    """Tableau de bord avec suggestions non exécutables."""

    def __init__(self, context):
        super().__init__(
            context,
            "Votre centre de contrôle",
            "L'essentiel de votre PC, de vos projets et de votre session.",
        )

        self.suggestion_engine = SuggestionEngine(
            cooldown_seconds=300
        )

        # Évalue les règles sans consommer le cooldown.
        self.candidate_engine = SuggestionEngine(
            cooldown_seconds=0
        )

        self.visible_suggestions = {}
        self.ignored_suggestions = set()
        self.last_context_refresh = 0.0
        # Évite de reconstruire des cartes Qt
        # lorsque leur contenu n'a pas changé.
        self._rendered_suggestions_signature = None

        # ----------------------------------------
        # Métriques système
        # ----------------------------------------

        metrics = QHBoxLayout()

        self.cpu = Metric("CPU")
        self.ram = Metric("MÉMOIRE")
        self.battery = Metric("BATTERIE")

        for metric in (
            self.cpu,
            self.ram,
            self.battery,
        ):
            metrics.addWidget(metric)

        self.body.addLayout(metrics)

        self.system_state = label(
            "En attente de la première mesure…",
            "status",
        )
        self.body.addWidget(self.system_state)

        # ----------------------------------------
        # Projet et mode
        # ----------------------------------------

        grid = QGridLayout()

        project = Card("REPRENDRE LE FIL")

        self.project = label(
            "Aucun projet actif",
            "subheading",
        )
        self.objective = label(
            "Aucun objectif mémorisé.",
            "muted",
        )

        project.body.addWidget(self.project)
        project.body.addWidget(self.objective)
        grid.addWidget(project, 0, 0)

        mode = Card("ENVIRONNEMENT")

        self.mode = label(
            "Aucun mode enregistré",
            "subheading",
        )

        mode.body.addWidget(self.mode)
        mode.body.addWidget(label(
            "Le mode enregistré décrit la dernière demande, "
            "pas les applications encore ouvertes.",
            "muted",
        ))

        grid.addWidget(mode, 0, 1)
        self.body.addLayout(grid)

        # ----------------------------------------
        # Alertes
        # ----------------------------------------

        alerts = Card(
            "DERNIÈRES ALERTES · DEPUIS LE DÉMARRAGE"
        )

        self.alerts = text_view(
            "Aucune alerte émise depuis le démarrage."
        )
        self.alerts.setMinimumHeight(55)
        self.alerts.setMaximumHeight(70)

        alerts.body.addWidget(self.alerts)
        self.body.addWidget(alerts)

        # ----------------------------------------
        # Actions existantes
        # ----------------------------------------

        actions = QHBoxLayout()

        for title, command in [
            ("Diagnostic", "diagnostic"),
            ("Sauvegarder la session", "sauvegarde ma session"),
            ("Mode Travail", "mode Travail"),
        ]:
            button = QPushButton(title)
            button.clicked.connect(
                lambda checked=False, text=command:
                    context.commands.submit(text)
            )
            actions.addWidget(button)

        self.body.addLayout(actions)

        # ----------------------------------------
        # Nouveau panneau de contexte
        # ----------------------------------------

        self.context_card = Card("CONTEXTE ACTUEL")

        self.context_label = label(
            "Analyse du contexte en attente…",
            "muted",
        )

        self.context_card.body.addWidget(
            self.context_label
        )

        self.body.addWidget(self.context_card)

        # ----------------------------------------
        # Nouveau panneau de suggestions
        # ----------------------------------------

        self.suggestions_card = Card(
            "SUGGESTIONS INTELLIGENTES"
        )

        self.suggestions_info = label(
            "Aucune suggestion disponible.",
            "muted",
        )

        self.suggestions_card.body.addWidget(
            self.suggestions_info
        )

        self.suggestions_layout = QVBoxLayout()

        self.suggestions_card.body.addLayout(
            self.suggestions_layout
        )

        self.body.addWidget(self.suggestions_card)
        self.body.addStretch()

        # Réutilisation du monitoring existant.
        context.monitor.updated.connect(self.snapshot)
        context.monitor.failed.connect(self.monitor_error)

    # --------------------------------------------
    # Chargement asynchrone
    # --------------------------------------------

    def load(self):
        """Charge l'accueil et les suggestions en arrière-plan."""

        data = self.context.service.home()

        context_service = getattr(
            self.context,
            "context_service",
            None,
        )

        if context_service is None:
            return data

        try:
            snapshot = context_service.collect()
        except Exception:
            return data

        # Le détecteur de restauration ne doit pas
        # bloquer l'accueil en cas d'erreur.
        restore_suggestions = ()

        try:
            mode = snapshot.active_mode

            if mode:
                restore_suggestions = (
                    suggest_environment_restore(mode)
                )
        except Exception:
            restore_suggestions = ()

        return {
            **data,
            "_context_snapshot": snapshot,
            "_environment_suggestions": restore_suggestions,
        }

    # --------------------------------------------
    # Affichage des données générales
    # --------------------------------------------

    def render(self, value):
        project = value.get("project")

        self.project.setText(
            project["path"].name
            if project
            else "Aucun projet actif"
        )

        self.objective.setText(
            (
                project.get("objective")
                or "Aucun objectif mémorisé."
            )
            if project
            else "Ouvrez un projet pour reprendre votre travail."
        )

        mode = value.get("mode")

        self.mode.setText(
            mode.capitalize()
            if mode
            else "Aucun mode enregistré"
        )

        context_snapshot = value.get(
            "_context_snapshot"
        )

        if context_snapshot is not None:
            self.last_context_refresh = time.monotonic()

            self.render_context(context_snapshot)

            restore_suggestions = value.get(
                "_environment_suggestions",
                (),
            )

            self.update_suggestions(
                context_snapshot,
                restore_suggestions=restore_suggestions,
            )

    # --------------------------------------------
    # Contexte
    # --------------------------------------------

    def render_context(self, snapshot):
        app = snapshot.active_app or "Inconnue"
        project = snapshot.active_project or "Aucun"
        mode = snapshot.active_mode or "Aucun"

        workspace = (
            str(snapshot.active_workspace)
            if snapshot.active_workspace is not None
            else "Inconnu"
        )

        self.context_label.setText(
            f"Application : {app}\n"
            f"Workspace : {workspace}\n"
            f"Projet : {project}\n"
            f"Mode : {mode}"
        )

    # --------------------------------------------
    # Suggestions
    # --------------------------------------------

    def update_suggestions(
        self,
        snapshot,
        restore_suggestions=(),
    ):
        """Fusionne les suggestions sans doublons."""

        # Suggestions habituelles de Jarvis.
        context_candidates = {
            item.id: item
            for item in self.candidate_engine.evaluate(
                snapshot
            )
        }

        mode = snapshot.active_mode

        # Le mode Travail est déjà actif :
        # inutile de proposer de l'activer.
        if mode == "travail":
            context_candidates = {
                suggestion_id: suggestion
                for suggestion_id, suggestion
                in context_candidates.items()
                if suggestion.action_id
                != "suggest_mode_travail"
            }

        # Ajouter les suggestions de restauration.
        restore_candidates = {
            item.id: item
            for item in restore_suggestions
        }

        candidates = {
            **context_candidates,
            **restore_candidates,
        }

        # Enlever les suggestions dont la cause
        # n'existe plus.
        for suggestion_id in tuple(
            self.visible_suggestions
        ):
            if suggestion_id not in candidates:
                del self.visible_suggestions[
                    suggestion_id
                ]

        # Une suggestion ignorée peut réapparaître
        # si le problème disparaît puis revient.
        self.ignored_suggestions.intersection_update(
            candidates.keys()
        )

        # Cooldown des suggestions contextuelles.
        new_suggestions = (
            self.suggestion_engine.evaluate(snapshot)
        )

        for suggestion in new_suggestions:
            if (
                suggestion.id in context_candidates
                and suggestion.id
                not in self.ignored_suggestions
            ):
                self.visible_suggestions[
                    suggestion.id
                ] = suggestion

        # Suggestions d'environnement :
        # leur état est vérifié à chaque analyse.
        # Une fois affichées, elles restent visibles
        # tant que le problème persiste.
        for suggestion in restore_suggestions:
            if (
                suggestion.id
                not in self.ignored_suggestions
            ):
                self.visible_suggestions[
                    suggestion.id
                ] = suggestion

        self.render_suggestions()

    def render_suggestions(self):
        """Actualise les cartes seulement si nécessaire."""

        suggestions = sorted(
            self.visible_suggestions.values(),
            key=lambda item: (
                -item.priority,
                item.id,
            ),
        )

        # Signature basée sur le contenu réellement
        # visible, pas sur l'identité des objets Python.
        signature = tuple(
            (
                item.id,
                item.title,
                item.description,
                item.action_id,
                item.priority,
            )
            for item in suggestions
        )

        # Aucune différence : conserver les widgets.
        if signature == self._rendered_suggestions_signature:
            return

        # Mémoriser l'état qui va être affiché.
        self._rendered_suggestions_signature = signature

        # Le contenu a changé : reconstruire les cartes.
        while self.suggestions_layout.count():
            item = self.suggestions_layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

        if not suggestions:
            self.suggestions_info.setText(
                "Aucune suggestion à afficher."
            )
            return

        self.suggestions_info.setText(
            f"{len(suggestions)} suggestion(s) disponibles."
        )

        for suggestion in suggestions:
            card = Card(suggestion.title)

            description = QLabel(
                suggestion.description
            )
            description.setWordWrap(True)

            card.body.addWidget(description)

            buttons = QHBoxLayout()

            preview = QPushButton(
                "Prévisualiser"
            )
            preview.clicked.connect(
                lambda checked=False, s=suggestion:
                    self.preview_suggestion(s)
            )

            ignore = QPushButton("Ignorer")
            ignore.clicked.connect(
                lambda checked=False, s=suggestion:
                    self.ignore_suggestion(s.id)
            )

            buttons.addWidget(preview)

            if resolve_action(suggestion) is not None:
                execute = QPushButton("Exécuter")

                execute.clicked.connect(
                    lambda checked=False, s=suggestion:
                        self.execute_suggestion(s)
                )

                buttons.addWidget(execute)

            buttons.addWidget(ignore)
            card.body.addLayout(buttons)

            self.suggestions_layout.addWidget(card)

    def preview_suggestion(self, suggestion):
        """Explique l'action sans jamais l'exécuter."""

        descriptions = {
            "suggest_mode_travail": (
                "Action envisagée : passer en mode Travail.\n"
                "Cela pourrait changer de workspace et "
                "ouvrir des applications configurées."
            ),
            "suggest_select_project": (
                "Action envisagée : choisir un projet "
                "à reprendre."
            ),
            "suggest_system_diagnostic": (
                "Action envisagée : demander un "
                "diagnostic système."
            ),
            "suggest_memory_diagnostic": (
                "Action envisagée : examiner "
                "l'utilisation de la mémoire vive."
            ),
            "suggest_disk_diagnostic": (
                "Action envisagée : examiner "
                "l'utilisation du stockage."
            ),
        }

        action = resolve_action(suggestion)

        description = descriptions.get(
            suggestion.action_id,
            action.description
            if action is not None
            else "Aucune action associée.",
        )

        if action is not None:
            description += (
                f"\n\nCommande prévue : "
                f"{action.command}"
            )

        QMessageBox.information(
            self,
            suggestion.title,
            (
                f"{suggestion.description}\n\n"
                f"{description}\n\n"
                "Aucune commande n'a été exécutée."
            ),
        )

    def execute_suggestion(self, suggestion):
        """Exécute une suggestion après confirmation explicite."""

        action = resolve_action(suggestion)

        if action is None:
            QMessageBox.warning(
                self,
                "Action indisponible",
                "Cette suggestion ne peut pas être exécutée.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Confirmer l'action Jarvis",
            (
                f"{suggestion.title}\n\n"
                f"{action.description}\n\n"
                f"Commande : {action.command}\n\n"
                "Autoriser Jarvis à exécuter cette commande ?"
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        accepted = submit_action(
            suggestion,
            self.context.commands,
        )

        if not accepted:
            QMessageBox.warning(
                self,
                "Commande non lancée",
                (
                    "Jarvis n'a pas accepté cette commande. "
                    "Une autre opération est peut-être en cours."
                ),
            )
            return

        # Masquer la suggestion pendant son traitement.
        # Le moteur de contexte détectera ensuite
        # si la situation a réellement changé.
        self.ignore_suggestion(suggestion.id)

    def ignore_suggestion(self, suggestion_id):
        """Masque une proposition tant que sa cause persiste."""

        self.ignored_suggestions.add(
            suggestion_id
        )

        self.visible_suggestions.pop(
            suggestion_id,
            None,
        )

        self.render_suggestions()

    # --------------------------------------------
    # Cycle de vie
    # --------------------------------------------

    def set_active(self, active):
        super().set_active(active)

        if active and self.context.monitor.latest:
            self.snapshot(self.context.monitor.latest)

    @Slot(object)
    def snapshot(self, value):
        if not self.active:
            return

        self.cpu.set_value(value.cpu)
        self.ram.set_value(value.ram)

        self.battery.set_value(
            value.battery.percent if value.battery else 0,
            (
                f"{value.battery.percent:.0f} %"
                if value.battery
                else "Non détectée"
            ),
        )

        self.system_state.setText(
            value.warning
            or "● Monitoring actif · mesures locales"
        )

        self.alerts.setPlainText(
            "\n".join(reversed(value.alerts))
        )

        # Ne pas interroger Hyprland à chaque mesure.
        if (
            time.monotonic()
            - self.last_context_refresh >= 15
        ):
            self.refresh()
            self.last_context_refresh = time.monotonic()

    @Slot(str)
    def monitor_error(self, error):
        if self.active:
            self.system_state.setText(
                f"Mesures indisponibles ({error})"
            )
