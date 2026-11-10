
"""Tests de la mémoire personnelle de Jarvis V1.6."""

import sqlite3

import pytest

from jarvis.memory.schema import initialize_memory
from jarvis.memory.service import MemoryService


@pytest.fixture
def memory_service(tmp_path):
    return MemoryService(tmp_path / "memory.sqlite3")


def test_add_and_get(memory_service):
    memory = memory_service.add_memory(
        "Je préfère Rust",
        category="preferences",
    )

    assert memory.id > 0
    assert memory.content == "Je préfère Rust"
    assert memory.category == "preferences"
    assert memory_service.get_memory(memory.id) == memory


def test_duplicate(memory_service):
    first = memory_service.add_memory("J'aime Python")
    second = memory_service.add_memory("J'aime Python")

    assert first.id == second.id
    assert len(memory_service.list_memories()) == 1


def test_update(memory_service):
    memory = memory_service.add_memory("Je préfère Rust")

    updated = memory_service.update_memory(
        memory.id, "Je préfère Python"
    )

    assert updated.content == "Je préfère Python"
    assert updated.created_at == memory.created_at


def test_delete(memory_service):
    memory = memory_service.add_memory("Souvenir temporaire")

    assert memory_service.delete_memory(memory.id)
    assert memory_service.get_memory(memory.id) is None
    assert not memory_service.delete_memory(memory.id)


def test_clear_preserves_history(memory_service):
    memory_service.add_memory("Souvenir 1")
    memory_service.add_memory("Souvenir 2")

    with sqlite3.connect(memory_service.db_path) as con:
        con.execute(
            "CREATE TABLE history (id INTEGER PRIMARY KEY)"
        )
        con.execute("INSERT INTO history VALUES (1)")

    assert memory_service.clear_memories() == 2
    assert memory_service.list_memories() == []

    with sqlite3.connect(memory_service.db_path) as con:
        count = con.execute(
            "SELECT COUNT(*) FROM history"
        ).fetchone()[0]

    assert count == 1


def test_persistence(tmp_path):
    path = tmp_path / "memory.sqlite3"

    first = MemoryService(path)
    memory = first.add_memory("Je travaille avec Python")

    second = MemoryService(path)
    assert second.get_memory(memory.id).content == (
        "Je travaille avec Python"
    )


def test_categories(memory_service):
    memory_service.add_memory(
        "J'aime Rust", category="preferences"
    )
    memory_service.add_memory(
        "Projet Jarvis", category="projects"
    )

    memories = memory_service.list_memories("projects")

    assert len(memories) == 1
    assert memories[0].content == "Projet Jarvis"


@pytest.mark.parametrize("content", [
    "",
    "    ",
    "x" * 2001,
])
def test_invalid_content(memory_service, content):
    with pytest.raises(ValueError):
        memory_service.add_memory(content)


def test_invalid_category(memory_service):
    with pytest.raises(ValueError):
        memory_service.add_memory(
            "Exemple", category="unknown"
        )


def test_explicit_only(memory_service):
    with pytest.raises(ValueError):
        memory_service.add_memory(
            "Exemple", source="automatic"
        )


def test_schema_idempotent(tmp_path):
    path = tmp_path / "memory.sqlite3"

    initialize_memory(path)
    initialize_memory(path)

    with sqlite3.connect(path) as con:
        count = con.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type = 'table' AND name = 'memories'"
        ).fetchone()[0]

    assert count == 1

# ==========================================
# V1.6 — RECHERCHE DES SOUVENIRS
# ==========================================


def test_search_memories(memory_service):
    memory_service.add_memory("Je programme en Rust")
    memory_service.add_memory("Jarvis utilise Python")
    memory_service.add_memory("Je joue au basket")

    results = memory_service.search_memories("Rust")

    assert len(results) == 1
    assert results[0].content == "Je programme en Rust"


def test_search_without_accents(memory_service):
    memory_service.add_memory(
        "Je préfère développer en Python"
    )

    results = memory_service.search_memories("prefere")

    assert len(results) == 1
    assert "préfère" in results[0].content


def test_search_after_update(memory_service):
    memory = memory_service.add_memory(
        "Je développe en Python"
    )

    memory_service.update_memory(
        memory.id, "Je développe en Rust"
    )

    assert memory_service.search_memories("Python") == []

    results = memory_service.search_memories("Rust")
    assert len(results) == 1
    assert results[0].id == memory.id


def test_search_after_delete(memory_service):
    memory = memory_service.add_memory(
        "Mon projet utilise Rust"
    )

    assert len(memory_service.search_memories("Rust")) == 1

    memory_service.delete_memory(memory.id)

    assert memory_service.search_memories("Rust") == []


def test_search_limit(memory_service):
    for index in range(10):
        memory_service.add_memory(
            f"Projet Python numéro {index}"
        )

    assert len(memory_service.search_memories("Python", 3)) == 3

    with pytest.raises(ValueError):
        memory_service.search_memories("Python", 0)

    with pytest.raises(ValueError):
        memory_service.search_memories("Python", 51)


def test_search_empty_query(memory_service):
    memory_service.add_memory("Je travaille avec Rust")

    assert memory_service.search_memories("") == []
    assert memory_service.search_memories("   ") == []
    assert memory_service.search_memories("!!!") == []


def test_search_fallback_without_fts(memory_service):
    memory_service.add_memory(
        "Je préfère programmer en Rust"
    )

    # Simule une base où FTS5 est indisponible.
    # Le test utilise exclusivement une base temporaire.
    with sqlite3.connect(memory_service.db_path) as con:
        for trigger in (
            "memories_fts_insert",
            "memories_fts_update",
            "memories_fts_delete",
        ):
            con.execute(f"DROP TRIGGER IF EXISTS {trigger}")

        con.execute("DROP TABLE IF EXISTS memories_fts")

    results = memory_service.search_memories("prefere")

    assert len(results) == 1
    assert results[0].content == (
        "Je préfère programmer en Rust"
    )
