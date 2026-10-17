#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "python-dotenv==1.2.4",
# ]
# ///
"""Import open Google Tasks into Super Productivity.

Reads the JSON output of ``gog tasks list <id> --all --json --results-only``
from stdin and creates one Super Productivity task per open Google Task that
is not yet in the import register. Google Tasks is never modified.
See ``plan/design.md`` for the full design.
"""

import json
import sqlite3
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Self, cast

type GoogleTask = dict[str, object]
"""One task object from the gog JSON output."""

type SpTaskBody = dict[str, object]
"""Request body for ``POST /tasks`` of the Super Productivity REST API."""

UNTITLED = "(ohne Titel)"


class InputError(Exception):
    """The data on stdin is not a usable list of Google Tasks."""


# --- Input -----------------------------------------------------------------


def _as_object(value: object) -> dict[str, object] | None:
    """Return a JSON object as a typed dict, or ``None`` for any other value.

    ``json.loads`` yields untyped containers; the cast only narrows the type
    after the runtime check, JSON object keys are always strings.
    """
    if not isinstance(value, dict):
        return None
    return dict(cast(dict[str, object], value))


def read_google_tasks(text: str) -> list[GoogleTask]:
    """Parse gog output into a list of Google Tasks.

    Raises ``InputError`` unless ``text`` is a JSON array of objects that each
    carry a string ``id``; the id is what the import register is keyed by.
    """
    try:
        data: object = json.loads(text)
    except json.JSONDecodeError as error:
        raise InputError(f"input is not valid JSON: {error}") from error
    if not isinstance(data, list):
        raise InputError("input must be a JSON array of Google Tasks")
    tasks: list[GoogleTask] = []
    for index, item in enumerate(cast(list[object], data)):
        task = _as_object(item)
        if task is None:
            raise InputError(f"element {index} is not a JSON object")
        if not isinstance(task.get("id"), str):
            raise InputError(f"element {index} has no string 'id'")
        tasks.append(task)
    return tasks


def open_tasks(tasks: Sequence[GoogleTask]) -> list[GoogleTask]:
    """Return only open Google Tasks, i.e. those with status ``needsAction``."""
    return [task for task in tasks if task.get("status") == "needsAction"]


# --- Mapping ---------------------------------------------------------------


def _text(mapping: dict[str, object], key: str) -> str:
    """Return ``mapping[key]`` stripped if it is a string, else ``""``."""
    value = mapping.get(key)
    return value.strip() if isinstance(value, str) else ""


def _link_lines(task: GoogleTask) -> list[str]:
    """Render ``links`` as Markdown list items; malformed entries are skipped.

    The label falls back from ``description`` to ``type`` because Keep links
    carry no description.
    """
    links = task.get("links")
    if not isinstance(links, list):
        return []
    lines: list[str] = []
    for entry in cast(list[object], links):
        link = _as_object(entry)
        if link is None:
            continue
        url = _text(link, "link")
        if not url:
            continue
        label = _text(link, "description") or _text(link, "type") or "link"
        lines.append(f"- [{label}]({url})")
    return lines


def to_sp_task(task: GoogleTask, tag_id: str) -> SpTaskBody:
    """Map a Google Task onto a Super Productivity task body.

    ``parent`` is ignored on purpose: subtasks are imported flat. ``due`` only
    ever carries a date (the Tasks API drops the time), so its first ten
    characters are taken as-is; converting time zones could shift the day.
    """
    body: SpTaskBody = {
        "title": _text(task, "title") or UNTITLED,
        "tagIds": [tag_id],
    }
    due = _text(task, "due")
    if due:
        body["dueDay"] = due[:10]
    links = "\n".join(_link_lines(task))
    blocks = [_text(task, "notes"), links, _text(task, "webViewLink")]
    notes = "\n\n".join(block for block in blocks if block)
    if notes:
        body["notes"] = notes
    return body


# --- Import register -------------------------------------------------------


class ImportRegister:
    """Records which Google Task was imported as which SP task.

    A Google Task found here is never imported again, even if its SP task was
    deleted later.
    """

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS imported ("
            " google_task_id TEXT PRIMARY KEY,"
            " sp_task_id TEXT NOT NULL,"
            " imported_at TEXT NOT NULL)"
        )
        self._connection.commit()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._connection.close()

    def contains(self, google_task_id: str) -> bool:
        """Return whether the Google Task has already been imported."""
        row = self._connection.execute(
            "SELECT 1 FROM imported WHERE google_task_id = ?", (google_task_id,)
        ).fetchone()
        return row is not None

    def add(self, google_task_id: str, sp_task_id: str) -> None:
        """Record a verified import; raises ``IntegrityError`` on duplicates."""
        self._connection.execute(
            "INSERT INTO imported (google_task_id, sp_task_id, imported_at)"
            " VALUES (?, ?, ?)",
            (google_task_id, sp_task_id, datetime.now(UTC).isoformat()),
        )
        self._connection.commit()


# --- Entry point -----------------------------------------------------------


def main(argv: Sequence[str]) -> int:
    """Run the import and return the process exit code."""
    del argv  # argument parsing follows in phase 3
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
