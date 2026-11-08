import sqlite3
import pytest
from jarvis.config import load_settings
from jarvis.persistence.sqlite import connect


def test_transaction_rolls_back_and_closes(tmp_path):
    path = tmp_path / "database.db"
    with connect(path) as con:
        con.execute("CREATE TABLE sample(value TEXT)")
        con.execute("INSERT INTO sample VALUES ('original')")
    with pytest.raises(sqlite3.ProgrammingError):
        con.execute("SELECT 1")
    with pytest.raises(RuntimeError):
        with connect(path) as con:
            con.execute("INSERT INTO sample VALUES ('rollback')")
            raise RuntimeError()
    with connect(path) as con:
        assert con.execute("SELECT * FROM sample").fetchall() == [("original",)]


def test_existing_schema_and_data_preserved(project):
    from jarvis.projects import manager, sessions
    with manager.database() as db:
        db.execute("INSERT INTO sessions(path,opened_at) VALUES (?,1)", (str(project),))
    sessions.init_sessions()
    sessions.init_sessions()
    with manager.database() as db:
        assert db.execute("SELECT objective FROM projects").fetchone() == ("Continuer",)
        assert db.execute("SELECT COUNT(*) FROM sessions").fetchone() == (1,)


def test_configuration_defaults_and_overrides(tmp_path):
    path = tmp_path / "config.toml"
    default = load_settings(path)
    assert default.workspaces == {"travail": 3, "gaming": 4, "etudes": 5}
    assert default.notion_desktop == "notion"
    path.write_text('projects_root = "~/Code"\neditors = ["codium"]\n[workspaces]\ntravail = 6\n')
    settings = load_settings(path)
    assert settings.projects_root.name == "Code"
    assert settings.editors == ("codium",)
    assert settings.workspaces == {"travail": 6, "gaming": 4, "etudes": 5}


@pytest.mark.parametrize("value", ['[workspaces]\ntravail=10', '[workspaces]\ntravail=true', 'editors=[]', 'terminal="bash -c"', 'unknown=1'])
def test_invalid_configuration(tmp_path, value):
    path = tmp_path / "config.toml"
    path.write_text(value)
    with pytest.raises(ValueError):
        load_settings(path)
