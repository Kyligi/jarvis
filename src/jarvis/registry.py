"""Catalogue unique : résolution sans effets de bord, aide et handlers explicites."""
from dataclasses import dataclass
from importlib.metadata import version
import re
from collections.abc import Callable

from jarvis.core.text import normalize, normalize_words, strip_address
from jarvis.monitoring import system, intelligence, diagnostics
from jarvis.projects import manager, sessions
from jarvis.modes import manager as modes
from jarvis.modules import projects as legacy_projects
from jarvis import omarchy
from jarvis.services import window_commands as windows
from jarvis.scenarios import commands as scenarios

Handler = Callable[..., str]


@dataclass(frozen=True)
class Command:
    id: str
    name: str
    description: str
    examples: tuple[str, ...]
    handler: Handler
    category: str
    aliases: tuple[str, ...] = ()
    pattern: str | None = None
    parameter: str | None = None

    def match(self, message: str) -> tuple[str | int, ...] | None:
        text = normalize(message)
        if text in {normalize(alias) for alias in self.aliases}:
            return ()
        if self.pattern is None:
            return None
        match = re.fullmatch(self.pattern, text)
        if match is None:
            return None
        raw = strip_address(message)
        # Extraire les arguments depuis l'original : casse et accents conservés.
        if self.parameter == "objective":
            return (raw.split(":", 1)[1].strip(),)
        if self.parameter == "file":
            return (re.split(r"\s+", raw, maxsplit=3)[3],)
        if self.parameter == "project":
            return (re.split(r"\s+", raw, maxsplit=2)[2],)
        if self.parameter == "workspace_number":
            return (int(match.group(1)),)
        if self.parameter == "window_move":
            return (match.group(1), int(match.group(2)))
        return match.groups()


@dataclass(frozen=True)
class ResolvedCommand:
    command: Command
    arguments: tuple[str | int, ...]

    def run(self) -> str:
        return self.command.handler(*self.arguments)


def rust_list() -> str:
    projects = legacy_projects.rust_projects()
    return "\n".join(str(p) for p in projects) if projects else "Aucun projet Rust détecté."


def rust_open(name: str) -> str:
    matches = [p for p in legacy_projects.rust_projects() if normalize_words(p.name) == normalize_words(name)]
    if len(matches) != 1:
        return "Projet introuvable ou nom ambigu. Utilise 'projets rust'."
    return legacy_projects.open_project(matches[0]) + "\n" + legacy_projects.git_summary(matches[0])


def modes_list() -> str:
    from jarvis.modes.profiles import load
    return "J.A.R.V.I.S. — MODES DISPONIBLES\n\n" + "\n".join(
        f"• {name.capitalize()} (workspace {profile['workspace']})"
        for name, profile in load().items()
    )


def help_text() -> str:
    lines = [f"J.A.R.V.I.S. V{version('jarvis')} — COMMANDES DISPONIBLES"]
    category = None
    for entry in COMMANDS:
        if entry.category != category:
            category = entry.category
            lines.extend(["", category.upper()])
        lines.append(f"• {entry.name}\n  {entry.description}")
        lines.append("  Exemples : " + " | ".join(entry.examples))
        seen = {normalize(e) for e in entry.examples}
        aliases = []
        for alias in entry.aliases:
            if normalize(alias) not in seen:
                aliases.append(alias)
                seen.add(normalize(alias))
        if aliases:
            lines.append("  Alias : " + " | ".join(aliases))
    return "\n".join(lines)


def exact(id: str, name: str, description: str, aliases: tuple[str, ...],
          handler: Handler, category: str) -> Command:
    return Command(id, name, description, (name,), handler, category, aliases)


COMMANDS = (
    exact("help", "aide", "Afficher toutes les commandes et leurs alias", ("aide", "help", "commandes"), help_text, "Général"),
    exact("system.status", "état système", "CPU, RAM, disque, uptime et batterie", ("état système", "statut système", "statut", "status", "monitoring", "état du pc"), system.system_status, "Monitoring"),
    exact("system.processes", "processus", "Processus les plus consommateurs de CPU", ("processus", "top processus"), system.top_processes, "Monitoring"),
    exact("system.diagnose", "diagnostic", "Rechercher les saturations", ("diagnostic", "diagnostic système"), system.diagnose, "Monitoring"),
    exact("system.battery", "batterie", "Charge et autonomie estimée", ("batterie", "état batterie"), system.battery_status, "Monitoring"),
    exact("system.sensors", "capteurs", "Températures AMD et capteurs Linux", ("capteurs", "températures", "temperatures"), intelligence.sensors_text, "Monitoring"),
    exact("system.history", "historique", "Statistiques CPU/RAM de la dernière heure", ("historique", "historique performances", "historique système"), intelligence.history_text, "Monitoring"),
    exact("system.slowdown", "pourquoi mon pc ralentit", "Analyser ressources, températures et processus", ("pourquoi mon pc ralentit", "analyse mon pc", "diagnostic avancé", "mon pc est lent"), diagnostics.explain_slowdown, "Monitoring"),
    Command("desktop.terminal", "ouvre un terminal", "Lancer le terminal configuré", ("ouvre un terminal", "lance foot"), omarchy.open_terminal, "Omarchy", pattern=r".*\b(?:ouvre|ouvrir|lance)\s+(?:un |le )?(?:terminal|foot)\b.*"),
    Command("desktop.workspace", "passe au workspace N", "Changer de workspace (1 à 9) ; bureau et espace acceptés", ("passe au workspace 2", "va au bureau 3"), lambda n: omarchy.change_workspace(int(n)), "Omarchy", pattern=r"(?=.*\b(?:passe|aller|va|active|change)\b).*\b(?:workspace|bureau|espace)\s+([1-9])\b.*"),
    exact("projects.list", "mes projets", "Lister les projets Rust et Python", ("mes projets", "liste mes projets"), manager.list_projects, "Projets"),
    exact("projects.rust.list", "projets Rust", "Découverte Rust historique à un ou deux niveaux", ("projets rust", "liste rust", "liste mes projets rust"), rust_list, "Projets"),
    Command("projects.rust.resume", "reprends mon projet Rust", "Reprendre le dernier projet Rust utilisé", ("reprends mon projet Rust", "reprendre mon projet Rust"), lambda: manager.resume_language("Rust"), "Projets", pattern=r"(?=.*rust)(?=.*(?:reprends|reprendre)).*"),
    exact("projects.python.resume", "reprends mon projet Python", "Reprendre le dernier projet Python utilisé", ("reprends mon projet python", "reprendre mon projet python"), lambda: manager.resume_language("Python"), "Projets"),
    Command("projects.open", "ouvre projet NOM", "Ouvrir un projet par son nom exact", ("ouvre projet MonProjet",), manager.open_named_project, "Projets", pattern=r"ouvre projet .+", parameter="project"),
    Command("projects.rust.open", "ouvre rust NOM", "Ouverture Rust historique", ("ouvre rust MonProjet",), rust_open, "Projets", pattern=r"ouvre rust .+", parameter="project"),
    exact("projects.active", "projet actif", "Afficher le dernier projet ouvert", ("projet actif",), manager.active_project_text, "Projets"),
    exact("projects.git", "état git", "Branche, commit et modifications (lecture seule)", ("état git", "git status"), manager.active_git, "Projets"),
    Command("projects.objective", "objectif projet : TEXTE", "Mémoriser l'objectif du projet actif (500 caractères)", ("objectif projet : Terminer le module",), manager.set_objective, "Projets", pattern=r"objectif projet\s*:.*", parameter="objective"),
    exact("projects.history", "sessions projets", "Dix dernières reprises de projets", ("sessions projets",), manager.recent_sessions, "Projets"),
    Command("sessions.track", "suis le fichier CHEMIN", "Suivre un fichier dans le projet actif", ("suis le fichier src/main.rs",), sessions.track_file, "Sessions", pattern=r"suis le fichier .+", parameter="file"),
    exact("sessions.files", "mes fichiers suivis", "Afficher les fichiers suivis", ("mes fichiers suivis", "affiche mes fichiers suivis"), sessions.files_text, "Sessions"),
    exact("sessions.save", "sauvegarde ma session", "Enregistrer projet, fichiers, Git et objectif", ("sauvegarde session", "sauvegarde ma session", "enregistre ma session"), sessions.save_session, "Sessions"),
    exact("sessions.restore", "reprends ma session", "Ouvrir le workspace Travail, l'éditeur et Foot", ("reprends ma session", "restaure ma session", "reprendre session"), sessions.restore_session, "Sessions"),
    exact("sessions.status", "état session", "Afficher la session sauvegardée du projet actif", ("état session", "ma session"), sessions.session_info, "Sessions"),
    *(Command(f"modes.{name}", f"mode {label}", description,
              (f"mode {label}", f"active le mode {label}", f"lancer le mode {label}"),
              lambda name=name: modes.activate_mode(name), "Modes",
              pattern=rf"(?:(?:active|activer|lance|lancer)\s+)?(?:le\s+)?mode\s+{name}")
      for name, label, description in (
          ("travail", "Travail", "Éditeur, terminal et projet actif — workspace Travail"),
          ("gaming", "Gaming", "Steam — workspace Gaming"),
          ("etudes", "Études", "Chrome et Notion via gtk-launch notion — workspace Études"),
      )),
    exact("modes.status", "mode actuel", "Afficher le dernier mode enregistré", ("mode actuel", "mode actif"), modes.mode_status, "Modes"),
    exact("modes.list", "mes modes", "Afficher les modes et leurs workspaces", ("mes modes", "liste les modes", "modes"), modes_list, "Modes"),
    exact("windows.list", "mes fenêtres", "Lister les fenêtres réelles avec leurs adresses", ("mes fenêtres", "liste mes fenêtres"), windows.inventory, "Fenêtres"),
    exact("windows.active", "fenêtre active", "Identifier la fenêtre active", ("fenêtre active",), windows.active, "Fenêtres"),
    exact("windows.desktops", "mes bureaux", "Lister les workspaces", ("mes bureaux",), windows.desktops, "Fenêtres"),
    Command("windows.workspace", "bureau N", "Afficher un bureau de 1 à 9", ("bureau 3",), windows.switch, "Fenêtres", pattern=r"bureau ([1-9])", parameter="workspace_number"),
    exact("windows.next", "bureau suivant", "Bureau suivant du moniteur", ("bureau suivant",), lambda: windows.step(1), "Fenêtres"),
    exact("windows.previous", "bureau précédent", "Bureau précédent du moniteur", ("bureau précédent",), lambda: windows.step(-1), "Fenêtres"),
    Command("windows.focus", "focus APPLICATION", "Cibler par classe, titre ou adresse ; sélection si ambigu", ("focus Foot",), lambda q: windows.action("focus", q), "Fenêtres", pattern=r"focus (.+)"),
    Command("windows.locate", "où est APPLICATION", "Rechercher par classe ou titre", ("où est Chrome",), windows.locate, "Fenêtres", pattern=r"ou est (.+)"),
    Command("windows.move", "déplace APPLICATION au bureau N", "Déplacer une fenêtre identifiée", ("déplace Foot au bureau 3",), lambda q, n: windows.action("move", q, n), "Fenêtres", pattern=r"deplace (.+) au bureau ([1-9])", parameter="window_move"),
    *(Command(f"windows.{side}", f"mets APPLICATION à {side}", "Placement en moitié d’écran flottante", (f"mets Foot à {side}",), lambda q, side=side: windows.action(side, q), "Fenêtres", pattern=rf"mets (.+) a {side}") for side in ("gauche", "droite")),
    exact("windows.center", "centre la fenêtre", "Centrer la fenêtre active si flottante", ("centre la fenêtre",), lambda: windows.action("center"), "Fenêtres"),
    exact("windows.float", "fenêtre flottante", "Rendre la fenêtre active flottante", ("fenêtre flottante",), lambda: windows.action("float"), "Fenêtres"),
    exact("windows.tile", "fenêtre mosaïque", "Replacer la fenêtre active en mosaïque", ("fenêtre mosaïque",), lambda: windows.action("tile"), "Fenêtres"),
    exact("windows.organize", "organise mon bureau", "Prévisualiser la remise en mosaïque des fenêtres non protégées", ("organise mon bureau",), lambda: windows.preview("bureau"), "Fenêtres"),
    *(exact(f"windows.layout.{name}", f"disposition {label}", "Prévisualiser ; confirmation obligatoire avant déplacement", (f"disposition {label}",), lambda name=name: windows.preview(name), "Fenêtres") for name, label in (("developpement", "développement"), ("etudes", "études"), ("gaming", "gaming"))),
    Command("windows.confirm", "confirme disposition CODE", "Appliquer le plan prévisualisé pendant 60 secondes", ("confirme disposition 1234abcd",), windows.confirm, "Fenêtres", pattern=r"confirme disposition ([0-9a-f]{8})"),
    exact("windows.cancel", "annule disposition", "Annuler la disposition en attente", ("annule disposition",), windows.cancel, "Fenêtres"),
    exact("scenarios.list", "mes scénarios", "Bibliothèque et fichiers invalides", ("mes scénarios", "liste mes scénarios", "scénarios"), scenarios.library, "Scénarios"),
    Command("scenarios.run", "lance scénario NOM", "Exécuter les étapes ; confirmation avant déplacement", ("lance scénario Révisions",), scenarios.launch, "Scénarios", pattern=r"(?:lance|lancer|execute) (?:le )?scenario (.+)"),
    Command("scenarios.preview", "prévisualise scénario NOM", "Simulation sans mutation du bureau ni des projets", ("prévisualise scénario Révisions",), scenarios.preview, "Scénarios", pattern=r"(?:previsualise|simule) (?:le )?scenario (.+)"),
    exact("scenarios.cancel", "annule scénario", "Annuler les étapes non commencées, sans fermer d’application", ("annule scénario", "annule le scénario"), scenarios.cancel, "Scénarios"),
    exact("scenarios.status", "état scénario", "Résultat et progression de la dernière exécution", ("état scénario", "état du scénario"), scenarios.status, "Scénarios"),
    exact("scenarios.history", "historique scénarios", "Les 100 dernières exécutions", ("historique scénarios", "historique des scénarios"), scenarios.history, "Scénarios"),
    Command("scenarios.confirm", "confirme scénario CODE", "Confirmer les déplacements annoncés pendant 60 secondes", ("confirme scénario 1234abcd",), scenarios.confirm, "Scénarios", pattern=r"confirme scenario ([0-9a-f]{8})"),
    exact("scenarios.open", "ouvre scénarios", "Ouvrir l’éditeur dans le HUD", ("ouvre scénarios", "ouvre les scénarios"), scenarios.open_page, "Scénarios"),
    Command("modes.configure", "configure mode NOM", "Ouvrir les paramètres du mode dans le HUD", ("configure mode Études",), scenarios.configure, "Modes", pattern=r"configure (?:le )?mode (.+)"),

)


def validate_registry(commands: tuple[Command, ...] = COMMANDS) -> None:
    ids: set[str] = set()
    aliases: dict[str, str] = {}
    for entry in commands:
        if entry.id in ids or not callable(entry.handler):
            raise ValueError(f"Commande invalide : {entry.id}")
        ids.add(entry.id)
        for alias in entry.aliases:
            key = normalize(alias)
            if key in aliases and aliases[key] != entry.id:
                raise ValueError(f"Alias ambigu : {key}")
            aliases[key] = entry.id
        if entry.pattern:
            re.compile(entry.pattern)


def resolve(message: str, category: str | None = None) -> ResolvedCommand | None:
    # Les paramètres peuvent contenir des mots d'autres commandes : privilégier
    # les routes structurées avant les anciennes formulations libres.
    ordered = sorted(COMMANDS, key=lambda c: c.id in {
        "desktop.terminal", "desktop.workspace", "projects.rust.resume",
    })
    for entry in ordered:
        if category is not None and entry.category != category:
            continue
        arguments = entry.match(message)
        if arguments is not None:
            return ResolvedCommand(entry, arguments)
    return None


def dispatch(message: str, category: str | None = None) -> str | None:
    resolved = resolve(message, category)
    return resolved.run() if resolved else None


validate_registry()
