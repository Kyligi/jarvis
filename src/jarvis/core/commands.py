import subprocess
import shutil
from jarvis.modules.projects import rust_projects, git_summary, open_project
from jarvis.modules.monitoring import system_status
from jarvis.memory.database import remember
from jarvis.commands import handle_system_command
from jarvis.registry import dispatch
from jarvis.projects.manager import handle_project_command

def execute(command: str) -> str:
    text = " ".join(command.lower().strip().split())
    if not text:
        return "Écris une commande."
    # V0.7 — Gestionnaire de projets
    try:
        project_result = handle_project_command(command)

        if project_result is not None:
            return project_result

    except Exception as error:
        return f"Erreur gestionnaire de projets : {error}"
    # Jarvis V0.4 : registre et monitoring
    try:
        registry_result = dispatch(command)
        if registry_result is not None:
            return registry_result
    except Exception as error:
        return f"Erreur monitoring : {error}"
    # Jarvis V0.3 : commandes Omarchy
    try:
        result = handle_system_command(command)
        if result is not None:
            return result
    except Exception as error:
        return f"Erreur Omarchy : {error}"
    if text.startswith("jarvis,"):
        text = text.removeprefix("jarvis,").strip()
    if "rust" in text and ("reprends" in text or "reprendre" in text):
        projects = rust_projects()
        if not projects:
            result = "Aucun Cargo.toml trouvé à 1 ou 2 niveaux sous ~/Projects."
        elif len(projects) > 1:
            result = "Plusieurs projets Rust détectés. Choisis un projet avec : ouvre rust NOM\n" + "\n".join(f"• {p.name}" for p in projects)
        else:
            project = projects[0]
            result = open_project(project) + "\n" + git_summary(project)
    elif text in {"projets rust", "liste rust", "liste mes projets rust"}:
        projects = rust_projects()
        result = "\n".join(str(p) for p in projects) if projects else "Aucun projet Rust détecté."
    elif text.startswith("ouvre rust "):
        name = text.removeprefix("ouvre rust ").strip()
        matches = [p for p in rust_projects() if p.name.lower() == name]
        result = (open_project(matches[0]) + "\n" + git_summary(matches[0])) if len(matches) == 1 else "Projet introuvable ou nom ambigu. Utilise 'projets rust'."
    elif text in {"statut", "status", "monitoring", "état du pc"}:
        result = system_status()
    elif text in {"aide", "help"}:
        result = "Commandes : aide | statut | projets rust | reprends mon projet Rust | ouvre rust NOM"
    else:
        result = "Commande inconnue. Tape 'aide'."
    try:
        remember(command, result)
    except OSError:
        result += "\n(Avertissement : historique non enregistré.)"
    return result
