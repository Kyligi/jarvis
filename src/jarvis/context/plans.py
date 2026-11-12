"""Plans d'actions contrôlés de Jarvis V1.7."""

from dataclasses import dataclass

MAX_STEPS = 5


@dataclass(frozen=True)
class PlanStep:
    """Une étape autorisée du plan."""

    id: str
    title: str
    command: str
    description: str
    requires_confirmation: bool = False


@dataclass(frozen=True)
class ActionPlan:
    """Plan immuable, sans capacité d'exécution."""

    id: str
    title: str
    description: str
    steps: tuple[PlanStep, ...]

    def preview(self) -> str:
        lines = [
            f"J.A.R.V.I.S. — {self.title}",
            self.description,
            "",
        ]

        for index, step in enumerate(self.steps, 1):
            lines.extend([
                f"{index}. {step.title}",
                f"   Commande : {step.command}",
                f"   {step.description}",
            ])

            if step.requires_confirmation:
                lines.append(
                    "   Confirmation requise"
                )

        lines.extend([
            "",
            "Aucune action n'a été exécutée.",
        ])

        return "\n".join(lines)


# Liste fermée des opérations autorisées.
# Aucune commande shell arbitraire n'est admise.
ALLOWED_STEPS = {
    "mode_travail": PlanStep(
        id="mode_travail",
        title="Activer le mode Travail",
        command="mode Travail",
        description=(
            "Appliquer le profil Travail configuré "
            "dans Jarvis."
        ),
        requires_confirmation=True,
    ),
    "diagnostic": PlanStep(
        id="diagnostic",
        title="Diagnostic système",
        command="diagnostic",
        description=(
            "Examiner l'état du système via Jarvis."
        ),
    ),
    "save_session": PlanStep(
        id="save_session",
        title="Sauvegarder la session",
        command="sauvegarde ma session",
        description=(
            "Enregistrer l'état de la session courante."
        ),
        requires_confirmation=True,
    ),
}


# Plans disponibles dans cette première version.
PLAN_DEFINITIONS = {
    "prepare_work": (
        "Préparer ma session de travail",
        "Active l'environnement Travail et vérifie le PC.",
        ("mode_travail", "diagnostic"),
    ),
    "save_and_check": (
        "Sauvegarder et vérifier ma session",
        "Sauvegarde la session avant un diagnostic.",
        ("save_session", "diagnostic"),
    ),
}


def build_plan(plan_id: str) -> ActionPlan:
    """Construit uniquement un plan préautorisé."""

    if not isinstance(plan_id, str):
        raise ValueError("Identifiant de plan invalide.")

    definition = PLAN_DEFINITIONS.get(plan_id)

    if definition is None:
        raise ValueError("Plan inconnu.")

    title, description, step_ids = definition

    if not 1 <= len(step_ids) <= MAX_STEPS:
        raise ValueError("Nombre d'étapes invalide.")

    if len(set(step_ids)) != len(step_ids):
        raise ValueError("Étapes dupliquées.")

    try:
        steps = tuple(
            ALLOWED_STEPS[step_id]
            for step_id in step_ids
        )
    except KeyError as error:
        raise ValueError(
            "Le plan contient une étape non autorisée."
        ) from error

    return ActionPlan(
        id=plan_id,
        title=title,
        description=description,
        steps=steps,
    )


def list_plans() -> tuple[ActionPlan, ...]:
    """Liste les plans disponibles sans les exécuter."""

    return tuple(
        build_plan(plan_id)
        for plan_id in PLAN_DEFINITIONS
    )
