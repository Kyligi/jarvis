"""Une connexion par opération : transaction, rollback et fermeture garantis."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from collections.abc import Iterator


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5)
    try:
        with connection:
            yield connection
    finally:
        connection.close()
