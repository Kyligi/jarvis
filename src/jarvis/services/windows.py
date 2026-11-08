"""Inventaire Hyprland, validations et actions Lua ciblées, sans dépendance Qt."""
from dataclasses import dataclass
import json
import re
import subprocess
from jarvis.core.text import normalize_words
from jarvis.integrations.desktop import focus_workspace


class WindowError(RuntimeError):
    pass


def workspace(number: int) -> int:
    if type(number) is not int or not 1 <= number <= 9:
        raise WindowError("Le bureau doit être un entier de 1 à 9.")
    return number


def address(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"0x[0-9a-fA-F]+", value):
        raise WindowError("Adresse de fenêtre invalide.")
    return value.lower()


@dataclass(frozen=True)
class Window:
    address: str
    app: str
    title: str
    workspace: int
    workspace_name: str
    monitor: int
    floating: bool
    pid: int
    fullscreen: int = 0

    @property
    def protected(self):
        return self.app.lower() in {"jarvis", "jarvis-hud"} or self.workspace_name == "special:jarvis"

    def describe(self):
        return f"{self.address} · {self.app} · {self.title} · bureau {self.workspace_name} · {'flottante' if self.floating else 'mosaïque'}"


def parse_windows(rows) -> list[Window]:
    try:
        if not isinstance(rows, list):
            raise ValueError()
        result = []
        for row in rows:
            ws = row["workspace"]
            if any(type(row[k]) is not int for k in ("monitor", "pid")) or type(ws["id"]) is not int:
                raise ValueError()
            if type(row["floating"]) is not bool or any(not isinstance(v, str) for v in (row["class"], row["title"], ws["name"])):
                raise ValueError()
            result.append(Window(address(row["address"]), row["class"], row["title"], ws["id"], ws["name"], row["monitor"], row["floating"], row["pid"], int(row.get("fullscreen", 0))))
        return result
    except (KeyError, TypeError, ValueError) as error:
        raise WindowError("Inventaire des fenêtres Hyprland invalide.") from error


def build_action(action: str, target: str, *values: int) -> str:
    target = address(target)
    window = f'window="address:{target}"'
    if action == "focus" and not values:
        return f"hl.dsp.focus({{{window}}})"
    if action == "move" and len(values) == 1:
        return f'hl.dsp.window.move({{{window},workspace="{workspace(values[0])}",follow=false}})'
    if action in {"float", "tile"} and not values:
        return f'hl.dsp.window.float({{{window},action="{"on" if action == "float" else "off"}"}})'
    if action == "center" and not values:
        return f"hl.dsp.window.center({{{window}}})"
    if action in {"resize", "position"} and len(values) == 2:
        lo = 1 if action == "resize" else -100000
        if any(type(v) is not int or not lo <= v <= 100000 for v in values):
            raise WindowError("Dimensions ou position invalides.")
        method = "resize" if action == "resize" else "move"
        return f"hl.dsp.window.{method}({{{window},x={values[0]},y={values[1]},relative=false}})"
    raise WindowError("Action ou paramètres non autorisés.")


def validate_resource(resource, value):
    """Valider les champs consommés avant de calculer une géométrie."""
    if resource in {"clients", "workspaces", "monitors"}:
        if not isinstance(value, list):
            raise ValueError("Liste attendue")
    elif not isinstance(value, dict):
        raise ValueError("Objet attendu")
    if resource in {"workspaces", "activeworkspace"}:
        for row in (value if resource == "workspaces" else ([value] if value else [])):
            if type(row["id"]) is not int or not isinstance(row["name"], str):
                raise ValueError("Workspace invalide")
    if resource == "monitors":
        for row in value:
            for key in ("id", "x", "y", "width", "height"):
                if type(row[key]) is not int:
                    raise ValueError("Moniteur invalide")
            if not isinstance(row["name"], str) or type(row["scale"]) not in {int, float} or not 0.1 <= row["scale"] <= 10:
                raise ValueError("Échelle invalide")
            if not 0 < row["width"] <= 100000 or not 0 < row["height"] <= 100000:
                raise ValueError("Dimensions invalides")
            reserved = row.get("reserved", [0, 0, 0, 0])
            if not isinstance(reserved, list) or len(reserved) != 4 or any(type(v) is not int or v < 0 for v in reserved):
                raise ValueError("Réservations invalides")
            if type(row.get("transform", 0)) is not int:
                raise ValueError("Rotation invalide")


class WindowService:
    def _run(self, *args):
        try:
            result = subprocess.run(["hyprctl", *args], capture_output=True, text=True, timeout=5, check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise WindowError("Hyprland indisponible ou délai dépassé.") from error
        if result.returncode or (args[0] == "dispatch" and result.stdout.strip().lower() != "ok"):
            raise WindowError("Action refusée par Hyprland.")
        return result.stdout

    def read(self, resource):
        if resource not in {"clients", "activewindow", "activeworkspace", "workspaces", "monitors"}:
            raise WindowError("Lecture non autorisée.")
        try:
            value = json.loads(self._run(resource, "-j"))
            validate_resource(resource, value)
            return value
        except (ValueError, TypeError, KeyError) as error:
            raise WindowError("Réponse JSON Hyprland invalide.") from error

    def windows(self):
        return parse_windows(self.read("clients"))

    def active(self):
        row = self.read("activewindow")
        return parse_windows([row])[0] if row else None

    def snapshot(self):
        return {"windows": self.windows(), "workspaces": self.read("workspaces"),
                "monitors": self.read("monitors"), "current": self.read("activeworkspace")}

    def search(self, query):
        if not isinstance(query, str) or not query.strip() or len(query) > 256:
            raise WindowError("Nom d’application ou titre invalide.")
        query = normalize_words(query)
        return [w for w in self.windows() if query == w.address or query in normalize_words(w.app) or query in normalize_words(w.title)]

    def in_workspace(self, number):
        return [w for w in self.windows() if w.workspace == workspace(number)]

    def validate(self, target):
        current = next((w for w in self.windows() if w.address == target.address), None)
        if current is None or (current.pid, current.app) != (target.pid, target.app):
            raise WindowError("Fenêtre fermée ou remplacée : actualisez la sélection.")
        if current.protected:
            raise WindowError("Fenêtre Jarvis protégée : aucune modification autorisée.")
        return current

    def act(self, action, target, *values):
        lua = build_action(action, target.address, *values)
        current = self.validate(target)
        if current.fullscreen and action != "focus":
            raise WindowError("Quittez le plein écran avant de modifier cette fenêtre.")
        if action in {"center", "resize", "position"} and not current.floating:
            raise WindowError("Cette action nécessite une fenêtre flottante.")
        self._run("dispatch", lua)

    def switch(self, number, style="command"):
        focus_workspace(workspace(number), style)

    def step(self, direction):
        if direction not in {-1, 1} or type(direction) is not int:
            raise WindowError("Direction invalide.")
        self._run("dispatch", 'hl.dsp.focus({workspace="m' + ('+1' if direction == 1 else '-1') + '"})')

    def half(self, target, side):
        if side not in {"gauche", "droite"}:
            raise WindowError("Côté invalide.")
        current = self.validate(target)
        if current.fullscreen:
            raise WindowError("Quittez le plein écran avant de placer cette fenêtre.")
        monitor = next((m for m in self.read("monitors") if m["id"] == current.monitor), None)
        if monitor is None:
            raise WindowError("Moniteur déconnecté.")
        width, height = int(monitor["width"] / monitor["scale"]), int(monitor["height"] / monitor["scale"])
        if monitor.get("transform", 0) % 2:
            width, height = height, width
        left, top, right, bottom = monitor.get("reserved", [0, 0, 0, 0])
        width, height = width - left - right, height - top - bottom
        x = monitor["x"] + left + (width // 2 if side == "droite" else 0)
        y = monitor["y"] + top
        self.act("float", target)
        self.act("resize", target, width // 2, height)
        self.act("position", target, x, y)


service = WindowService()


def application_class(value: str) -> str:
    # StartupWMClass lu dans notion.desktop sur cette installation Omarchy.
    if re.fullmatch(r"chrome-www\.notion\.so__-[\w -]+", value, re.IGNORECASE):
        return "notion"
    aliases = {"google-chrome-stable": "google-chrome", "chromium-browser": "chromium", "dev.zed.zed": "zed"}
    return aliases.get(value.lower(), value.lower())


def existing_application(candidates):
    """Classe exacte uniquement ; ne jamais confondre un titre avec une application."""
    classes = {application_class(c) for c in candidates}
    return [w for w in service.windows() if application_class(w.app) in classes and not w.protected]
