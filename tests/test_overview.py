from jarvis.projects import manager, sessions
from jarvis.services.overview import OverviewService


def test_overview_real_services_temporary_data(project, monkeypatch):
    service = OverviewService()
    assert service.home()["project"]["path"] == project
    items = service.projects()
    assert items[0]["objective"] == "Continuer"
    assert items[0]["last_opened"] == 1
    monkeypatch.setattr(manager, "git_summary", lambda path: "Git simulé")
    assert service.project_details(project) == "Git simulé"
    assert "non reconnu" in service.project_details(project.parent)
    monkeypatch.setattr(sessions, "git_summary", lambda path: "snapshot")
    sessions.track_file("Ébauche.py")
    sessions.save_session()
    data = service.session()
    assert "Continuer" in data["saved"]
    assert "Ébauche.py" in data["files"]


def test_overview_without_data():
    service = OverviewService()
    assert service.home() == {"project": None, "mode": None}
    assert service.projects() == []
    assert "Aucun projet" in service.session()["project"]
