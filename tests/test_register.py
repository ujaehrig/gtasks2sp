"""Tests for the SQLite-backed import register."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tasks2sp import ImportRegister


def test_creates_missing_directory_and_starts_empty(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "dir" / "import.sqlite"

    with ImportRegister(path) as register:
        assert not register.contains("g-1")

    assert path.is_file()


def test_add_then_contains(tmp_path: Path) -> None:
    with ImportRegister(tmp_path / "r.sqlite") as register:
        register.add("g-1", "sp-1")

        assert register.contains("g-1")
        assert not register.contains("g-2")


def test_entries_persist_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "r.sqlite"
    with ImportRegister(path) as register:
        register.add("g-1", "sp-1")

    with ImportRegister(path) as register:
        assert register.contains("g-1")


def test_stores_sp_task_id_and_utc_timestamp(tmp_path: Path) -> None:
    path = tmp_path / "r.sqlite"
    before = datetime.now(UTC)
    with ImportRegister(path) as register:
        register.add("g-1", "sp-1")

    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT sp_task_id, imported_at FROM imported WHERE google_task_id = ?",
            ("g-1",),
        ).fetchone()
    connection.close()

    assert row[0] == "sp-1"
    imported_at = datetime.fromisoformat(row[1])
    assert imported_at.tzinfo is not None
    assert before <= imported_at <= datetime.now(UTC)


def test_adding_the_same_google_task_twice_fails(tmp_path: Path) -> None:
    with ImportRegister(tmp_path / "r.sqlite") as register:
        register.add("g-1", "sp-1")

        with pytest.raises(sqlite3.IntegrityError):
            register.add("g-1", "sp-2")


def test_connection_is_closed_on_exit(tmp_path: Path) -> None:
    register = ImportRegister(tmp_path / "r.sqlite")
    with register:
        pass

    with pytest.raises(sqlite3.ProgrammingError):
        register.contains("g-1")
