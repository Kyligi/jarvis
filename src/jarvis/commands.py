
import re
import unicodedata

from jarvis.omarchy import (
    open_terminal,
    change_workspace,
    work_mode,
)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(
        c for c in text
        if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", text).strip()


def handle_system_command(message: str) -> str | None:
    text = normalize(message)
    text = re.sub(r"^jarvis[, :]*", "", text)

    if re.search(
        r"\b(ouvre|ouvrir|lance)\s+(un |le )?(terminal|foot)\b",
        text,
    ):
        return open_terminal()

    match = re.search(
        r"\b(?:workspace|bureau|espace)\s+([1-9])\b",
        text,
    )

    if match and re.search(
        r"\b(passe|aller|va|active|change)\b",
        text,
    ):
        return change_workspace(int(match.group(1)))

    if re.search(
        r"\b(active|activer|lance)\s+(le )?mode travail\b",
        text,
    ):
        return work_mode()

    return None
