"""Lectures à la demande ; aucun Git ni SQLite dans les widgets."""
from pathlib import Path

from jarvis.modes import manager as modes
from jarvis.monitoring import intelligence, system
from jarvis.projects import manager, sessions


class OverviewService:
    def home(self) -> dict:
        return {"project": manager.get_active_project(), "mode": modes.current_mode()}

    def projects(self) -> list[dict]:
        found = manager.discover_projects()
        with manager.database() as db:
            memory = {row[0]: row[1:] for row in db.execute(
                "SELECT path, objective, last_opened FROM projects"
            )}
        return [dict(p, objective=memory.get(str(p["path"]), ("", 0))[0],
                     last_opened=memory.get(str(p["path"]), ("", 0))[1]) for p in found]

    def project_details(self, path: Path) -> str:
        allowed = {p["path"] for p in manager.discover_projects()}
        if path.resolve() not in allowed:
            return "Projet indisponible ou non reconnu. Actualise la liste."
        return manager.git_summary(path)

    def session(self) -> dict:
        return {"project": manager.active_project_text(),
                "saved": sessions.session_info(),
                "files": sessions.files_text(),
                "history": manager.recent_sessions()}

    def system(self) -> dict:
        return {"history": intelligence.history_text(), "processes": system.top_processes()}

    def modes(self) -> dict:
        return {"mode": modes.current_mode()}
