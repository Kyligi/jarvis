"""Présentation textuelle et plans collectifs confirmés, partagés avec le HUD."""
from dataclasses import dataclass
from functools import wraps
import secrets
import time
from jarvis.services.windows import service, Window, WindowError, application_class


def readable(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (WindowError, RuntimeError) as error:
            return str(error)
    return wrapped


def describe(rows):
    return "\n".join(w.describe() for w in rows) or "Aucune fenêtre."


@readable
def inventory():
    return describe(service.windows())


@readable
def active():
    window = service.active()
    return window.describe() if window else "Aucune fenêtre active."


@readable
def desktops():
    state = service.snapshot()
    return "Bureau courant : " + str(state["current"].get("name", "aucun")) + "\n" + "\n".join(
        f"Bureau {w['name']} · {w.get('windows', 0)} fenêtre(s)" for w in state["workspaces"])


@readable
def switch(number: int):
    service.switch(number)
    return f"Bureau {number} affiché."


@readable
def step(direction: int):
    service.step(direction)
    return "Bureau changé sur le moniteur courant."


@readable
def locate(query: str):
    return describe(service.search(query))


@readable
def action(action: str, query: str | None = None, number: int | None = None):
    rows = service.search(query) if query else [service.active()]
    rows = [w for w in rows if w]
    if not rows:
        return "Aucune fenêtre correspondante."
    if len(rows) > 1:
        return "Plusieurs fenêtres : choisissez une adresse dans la page Fenêtres ou remplacez APPLICATION par son adresse.\n" + describe(rows)
    target = rows[0]
    try:
        if action in {"gauche", "droite"}:
            service.half(target, action)
            return "Placement flottant demandé : " + target.describe()
        service.act(action, target, *(() if number is None else (number,)))
    except WindowError as error:
        return f"Action interrompue (des étapes peuvent avoir été appliquées) : {error}"
    return "Action effectuée : " + target.describe()


@dataclass(frozen=True)
class Plan:
    name: str
    steps: tuple[tuple[Window, int, str], ...]
    expires: float
    token: str
    notes: tuple[str, ...]


pending: Plan | None = None


def build_plan(name: str, workspace=None):
    """Construction pure du plan ; seules des lectures Hyprland sont effectuées."""
    rows = service.windows()
    notes, steps = [], []
    profiles = {
        "developpement": (3, (("code", "code-oss", "codium", "zed", "dev.zed.zed"), ("foot",))),
        "etudes": (5, (("notion",), ("google-chrome", "chromium", "chrome"))),
        "gaming": (4, (("steam",),)),
    }
    if name == "bureau":
        current = service.read("activeworkspace")["id"]
        for w in rows:
            if w.workspace == current and not w.protected and not w.fullscreen and 1 <= current <= 9:
                steps.append((w, current, "tile"))
        notes.append("Mosaïque gérée par le layout Hyprland actuel, sans ordre exact garanti.")
    elif name in profiles:
        number, groups = profiles[name]
        if workspace is not None:
            from jarvis.services.windows import workspace as validate_workspace
            number = validate_workspace(workspace)
        for index, classes in enumerate(groups):
            matches = [w for w in rows if application_class(w.app) in classes and not w.protected]
            if len(matches) != 1:
                notes.append(f"{' / '.join(classes)} : {'absente, aucun lancement' if not matches else 'plusieurs fenêtres, choisir manuellement dans Fenêtres'}.")
                continue
            w = matches[0]
            if w.fullscreen:
                notes.append(f"{w.app} : plein écran préservé.")
                continue
            steps.append((w, number, "move" if name == "gaming" else ("gauche" if index == 0 else "droite")))
        notes.append("Réutilisation uniquement ; aucun jeu déplacé, aucune application lancée.")
    else:
        raise WindowError("Disposition inconnue.")
    return Plan(name, tuple(steps), time.monotonic() + 60, secrets.token_hex(4), tuple(notes))


@readable
def preview(name: str):
    global pending
    pending = None
    plan = build_plan(name)
    if not plan.steps:
        return "Aucune action à appliquer.\n" + "\n".join(plan.notes)
    pending = plan
    steps, notes = plan.steps, plan.notes
    return "Prévisualisation (valable 60 s) :\n" + "\n".join(
        f"{w.describe()} → bureau {number}, {kind}" for w, number, kind in steps
    ) + "\n" + "\n".join(notes) + f"\nConfirmer avec : confirme disposition {pending.token}\nAnnuler : annule disposition"


@readable
def confirm(token: str):
    global pending
    plan = pending
    pending = None
    if plan is None or token != plan.token or time.monotonic() > plan.expires:
        return "Confirmation absente, invalide ou expirée. Demandez une nouvelle disposition."
    # Revalider l'ensemble avant la première mutation, puis chaque étape.
    for target, _, _ in plan.steps:
        current = service.validate(target)
        if (current.workspace, current.monitor, current.floating, current.fullscreen) != (target.workspace, target.monitor, target.floating, target.fullscreen):
            return "Organisation modifiée depuis la prévisualisation : recommencez."
    results = []
    for target, number, kind in plan.steps:
        try:
            if kind == "tile":
                service.act("tile", target)
            else:
                service.act("move", target, number)
                if kind != "move":
                    service.half(target, kind)
            results.append(f"{target.address} : appliqué")
        except WindowError as error:
            results.append(f"{target.address} : échec partiel possible — {error}")
            break
    return "Résultat de disposition (arrêt au premier échec) :\n" + "\n".join(results)


def cancel():
    global pending
    pending = None
    return "Disposition annulée."


def execute_plan(plan, cancelled=lambda: False):
    """Exécution typée : les erreurs remontent au moteur, jamais converties en succès."""
    for window, _, _ in plan.steps:
        current = service.validate(window)
        if current.fullscreen or (current.workspace, current.monitor, current.floating) != (window.workspace, window.monitor, window.floating):
            raise WindowError("Organisation modifiée : recommencez la prévisualisation.")
    completed = 0
    for window, number, kind in plan.steps:
        if cancelled():
            return ('cancelled', f'{completed} fenêtre(s) traitée(s), suivantes annulées ; aucun rollback.')
        if kind == 'tile':
            service.act('tile', window)
        else:
            service.act('move', window, number)
            if kind != 'move':
                service.half(window, kind)
        completed += 1
    return f'{completed} fenêtre(s) traitée(s). ' + '\n'.join(plan.notes)
