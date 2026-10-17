"""Tests for reading and filtering the gog output."""

import json
from pathlib import Path

import pytest

from tasks2sp import InputError, open_tasks, read_google_tasks

FIXTURE = Path(__file__).parent / "fixtures" / "gog_tasks.json"


def test_reads_real_gog_output() -> None:
    tasks = read_google_tasks(FIXTURE.read_text(encoding="utf-8"))

    assert len(tasks) == 7
    assert tasks[0]["title"] == "Offen mit Datum in der Vergangenheit"


def test_reads_empty_array() -> None:
    assert read_google_tasks("[]") == []


def test_rejects_invalid_json() -> None:
    with pytest.raises(InputError, match="not valid JSON"):
        read_google_tasks("not json")


def test_rejects_json_object_instead_of_array() -> None:
    with pytest.raises(InputError, match="JSON array"):
        read_google_tasks(json.dumps({"tasks": []}))


def test_rejects_array_element_that_is_not_an_object() -> None:
    with pytest.raises(InputError, match="element 1 is not a JSON object"):
        read_google_tasks(json.dumps([{"id": "a"}, "b"]))


def test_rejects_task_without_string_id() -> None:
    with pytest.raises(InputError, match="element 0 has no string 'id'"):
        read_google_tasks(json.dumps([{"title": "x"}]))


def test_open_tasks_keeps_only_needs_action() -> None:
    tasks = read_google_tasks(FIXTURE.read_text(encoding="utf-8"))

    result = open_tasks(tasks)

    assert [task["status"] for task in result] == ["needsAction"] * 6
    assert "Erledigt" not in [task.get("title") for task in result]


def test_open_tasks_drops_tasks_without_status() -> None:
    assert open_tasks([{"id": "a"}]) == []
