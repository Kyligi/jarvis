"""Normalisation des mots de commande uniquement, jamais des paramètres."""
import re
import unicodedata


def strip_address(text: str) -> str:
    return re.sub(r"^jarvis\b[\s,:]*", "", text.strip(), flags=re.IGNORECASE)


def normalize_words(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def normalize(text: str) -> str:
    return normalize_words(strip_address(text))
