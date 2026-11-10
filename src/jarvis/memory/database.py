from datetime import datetime, timezone

from jarvis.config import settings
from jarvis.persistence.sqlite import connect

DB = settings.data_dir / "memory.sqlite3"


def remember(command: str, result: str) -> None:
    DB.parent.mkdir(parents=True, exist_ok=True)
    with connect(DB) as con:
        con.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, at TEXT NOT NULL, command TEXT NOT NULL, result TEXT NOT NULL)")
        con.execute("INSERT INTO history(at, command, result) VALUES (?,?,?)", (datetime.now(timezone.utc).isoformat(), command, result))
