"""Lecture Git bornée aux trois requêtes de J.A.R.V.I.S."""
import logging
from pathlib import Path
import subprocess

ALLOWED_QUERIES = {
    ("branch", "--show-current"),
    ("log", "-1", "--format=%h %s"),
    ("status", "--short", "--untracked-files=normal"),
}


def read_git(path: Path, *args: str) -> str | None:
    if args not in ALLOWED_QUERIES:
        raise ValueError("Requête Git non autorisée")
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *args], capture_output=True,
            text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        logging.getLogger(__name__).warning("git_unavailable", extra={
            "error_type": type(error).__name__,
        })
        return None
    if result.returncode != 0:
        logging.getLogger(__name__).warning("git_query_failed")
        return None
    return result.stdout.strip()
