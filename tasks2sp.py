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

import argparse
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Self, cast

from dotenv import load_dotenv

type GoogleTask = dict[str, object]
"""One task object from the gog JSON output."""

type SpTaskBody = dict[str, object]
"""Request body for ``POST /tasks`` of the Super Productivity REST API."""

UNTITLED = "(ohne Titel)"

EXIT_OK = 0
"""Every open Google Task is imported or was imported before."""
EXIT_FAILED_TASKS = 1
"""At least one task failed; all others were processed."""
EXIT_PRECHECK = 2
"""Configuration, input or precheck failed; nothing was created."""

DEFAULT_API = "http://127.0.0.1:3876"
DEFAULT_IMPORT_TAG = "gtask"
DEFAULT_DB = "~/.local/share/tasks2sp/import.sqlite"
TODAY_TAG_ID = "TODAY"
"""Id of Super Productivity's built-in Today tag, which is a date query."""


class InputError(Exception):
    """The data on stdin is not a usable list of Google Tasks."""


class ConfigError(Exception):
    """A required setting is missing."""


class PrecheckError(Exception):
    """Super Productivity is not ready for an import."""


class SpError(Exception):
    """Any failure talking to the Super Productivity REST API."""


class UnreachableError(SpError):
    """The REST API does not answer at all."""


class AuthError(SpError):
    """The REST API rejected the access token."""


class ApiError(SpError):
    """The REST API answered with an error or an unexpected response."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class VerificationError(Exception):
    """A created task does not hold the fields that were sent."""


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

    def __init__(self, path: Path | None) -> None:
        """Open the register at ``path``; ``None`` opens an empty in-memory one.

        The in-memory variant lets a dry run work without creating a file.
        """
        if path is None:
            self._connection = sqlite3.connect(":memory:")
        else:
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


# --- Super Productivity client ---------------------------------------------


class SpClient:
    """Thin client for the local Super Productivity REST API.

    Every response is an envelope ``{"ok": bool, "data"|"error": ...}``; this
    class unwraps ``data`` and turns everything else into an ``SpError``. The
    token is only ever sent as a header and never put into an error message.
    """

    def __init__(self, base_url: str, token: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout

    def health(self) -> dict[str, object]:
        """Return the ``/health`` payload (``server``, ``rendererReady``)."""
        return self._object(self._request("GET", "/health"))

    def tags(self) -> list[dict[str, object]]:
        """Return all tags."""
        data = self._request("GET", "/tags")
        items = cast(list[object], data) if isinstance(data, list) else None
        tags = [_as_object(item) for item in items or []]
        if items is None or any(tag is None for tag in tags):
            raise ApiError("INVALID_RESPONSE", "expected a list of JSON objects")
        return [tag for tag in tags if tag is not None]

    def create_task(self, body: SpTaskBody) -> dict[str, object]:
        """Create a task and return it as the API stored it."""
        return self._object(self._request("POST", "/tasks", body))

    def get_task(self, task_id: str) -> dict[str, object]:
        """Read a task back by its id."""
        return self._object(self._request("GET", f"/tasks/{task_id}"))

    @staticmethod
    def _object(data: object) -> dict[str, object]:
        result = _as_object(data)
        if result is None:
            raise ApiError("INVALID_RESPONSE", "expected a JSON object")
        return result

    def _request(self, method: str, path: str, body: object = None) -> object:
        request = urllib.request.Request(
            self._base_url + path,
            method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                status: int = response.status
                raw: bytes = response.read()
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read()
        except (urllib.error.URLError, OSError) as error:
            raise UnreachableError(
                f"cannot reach Super Productivity at {self._base_url} ({error}); "
                "start the desktop app and enable "
                "Settings -> Misc -> Enable local REST API"
            ) from error
        return self._unwrap(status, raw)

    @staticmethod
    def _unwrap(status: int, raw: bytes) -> object:
        if status == 401:
            raise AuthError(
                "the API rejected the token; copy it from "
                "Settings -> Misc -> Access Token into SP_TOKEN"
            )
        try:
            envelope = _as_object(json.loads(raw))
        except ValueError:
            envelope = None
        if envelope is None:
            raise ApiError("INVALID_RESPONSE", f"HTTP {status}, body is not JSON")
        if envelope.get("ok") is True and 200 <= status < 300:
            return envelope.get("data")
        error = _as_object(envelope.get("error")) or {}
        raise ApiError(
            _text(error, "code") or f"HTTP_{status}",
            _text(error, "message") or "request failed",
        )


# --- Precheck --------------------------------------------------------------


def precheck(client: SpClient, tag_name: str) -> str:
    """Check that Super Productivity can take an import; return the tag id.

    Raises ``PrecheckError`` (or an ``SpError`` from the client) so that the
    caller can stop before any task is created.
    """
    if tag_name.casefold() == "today":
        raise PrecheckError(
            "'Today' is a date query in Super Productivity, not a usable tag"
        )
    health = client.health()
    if health.get("server") != "up" or health.get("rendererReady") is not True:
        raise PrecheckError(f"Super Productivity is not ready: {health}")
    tags = client.tags()
    matches = [t for t in tags if _text(t, "title").casefold() == tag_name.casefold()]
    if not matches:
        available = ", ".join(
            _text(t, "title") for t in tags if t.get("id") != TODAY_TAG_ID
        )
        raise PrecheckError(
            f"import tag '{tag_name}' does not exist; create it in Super "
            f"Productivity first (available: {available or 'none'})"
        )
    if len(matches) > 1:
        raise PrecheckError(f"import tag '{tag_name}' is ambiguous")
    tag_id = _text(matches[0], "id")
    if tag_id == TODAY_TAG_ID:
        raise PrecheckError(
            "the Today tag is a date query in Super Productivity, not a usable tag"
        )
    return tag_id


# --- Import ----------------------------------------------------------------


def verify(expected: SpTaskBody, actual: Mapping[str, object]) -> None:
    """Raise ``VerificationError`` if ``actual`` lost any field of ``expected``.

    The API silently drops fields outside its allow-list, so a successful
    response alone does not prove the task holds what was sent. Tags only need
    to be present: the app may add tags of its own.
    """
    mismatched: list[str] = []
    for key, value in expected.items():
        stored = actual.get(key)
        if key == "tagIds":
            wanted = set(cast(list[object], value))
            have: set[object] = (
                set(cast(list[object], stored)) if isinstance(stored, list) else set()
            )
            if not wanted <= have:
                mismatched.append(key)
        elif stored != value:
            mismatched.append(key)
    if mismatched:
        raise VerificationError(
            f"verification failed for fields: {', '.join(mismatched)}"
        )


@dataclass
class Summary:
    """Counters reported at the end of a run."""

    read: int = 0
    open: int = 0
    imported: int = 0
    already: int = 0
    failed: int = 0

    def line(self, dry_run: bool) -> str:
        """Render the summary for stderr."""
        verb = "would be imported" if dry_run else "imported"
        return (
            f"{self.read} read, {self.open} open, {self.imported} {verb}, "
            f"{self.already} already imported, {self.failed} failed"
        )


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def import_tasks(
    tasks: Sequence[GoogleTask],
    client: SpClient,
    register: ImportRegister,
    tag_id: str,
    dry_run: bool,
) -> Summary:
    """Import every open, not yet registered Google Task; report on stderr.

    A task is registered only after its SP task was created and verified, so
    an interruption in between can cause a duplicate, never a lost task. A
    failing task is reported and skipped; it is retried on the next run.
    """
    pending = open_tasks(tasks)
    summary = Summary(read=len(tasks), open=len(pending))
    for position, task in enumerate(pending, start=1):
        google_id = cast(str, task["id"])
        body = to_sp_task(task, tag_id)
        prefix = f"[{position}/{len(pending)}]"
        if register.contains(google_id):
            summary.already += 1
            _log(f"{prefix} already imported: {body['title']}")
            continue
        if dry_run:
            summary.imported += 1
            _log(f"{prefix} would import: {body['title']}")
            continue
        try:
            created = client.create_task(body)
            sp_id = _text(created, "id")
            verify(body, client.get_task(sp_id))
        except (SpError, VerificationError) as error:
            summary.failed += 1
            _log(f"{prefix} FAILED: {body['title']}: {error}")
            continue
        register.add(google_id, sp_id)
        summary.imported += 1
        _log(f"{prefix} imported: {body['title']} -> {sp_id}")
    return summary


# --- Configuration and entry point -----------------------------------------


@dataclass(frozen=True)
class Config:
    """Settings read from the environment and the ``.env`` file."""

    token: str
    api: str
    import_tag: str
    db_path: Path


def load_config(env: Mapping[str, str]) -> Config:
    """Build the configuration; empty optional values fall back to defaults."""
    token = env.get("SP_TOKEN", "").strip()
    if not token:
        raise ConfigError("SP_TOKEN is not set (see .env.example)")
    return Config(
        token=token,
        api=env.get("SP_API") or DEFAULT_API,
        import_tag=env.get("SP_IMPORT_TAG") or DEFAULT_IMPORT_TAG,
        db_path=Path(env.get("TASKS2SP_DB") or DEFAULT_DB).expanduser(),
    )


def default_env_file(script: Path = Path(__file__)) -> Path:
    """Return the ``.env`` next to the real script file.

    Symlinks are resolved so that a link in e.g. ``~/bin`` still finds the
    ``.env`` in the project directory instead of looking next to the link.
    """
    return script.resolve().with_name(".env")


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Import open Google Tasks from gog JSON on stdin into Super "
            "Productivity. Example: gog tasks list <id> --all --json "
            "--results-only | tasks2sp.py"
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would be imported; write neither tasks nor register",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=default_env_file(),
        help="settings file (default: .env next to this script, symlinks "
        "resolved); the environment takes precedence",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    """Run the import and return the process exit code."""
    args = _parse_args(argv)
    dry_run: bool = args.dry_run
    load_dotenv(args.env_file, override=False)
    try:
        config = load_config(os.environ)
        tasks = read_google_tasks(sys.stdin.read())
        client = SpClient(config.api, config.token)
        tag_id = precheck(client, config.import_tag)
    except (ConfigError, InputError, PrecheckError, SpError) as error:
        _log(f"error: {error}")
        return EXIT_PRECHECK
    # a dry run must not create the register file just to find it empty
    db_path = None if dry_run and not config.db_path.exists() else config.db_path
    with ImportRegister(db_path) as register:
        summary = import_tasks(tasks, client, register, tag_id, dry_run)
    _log(summary.line(dry_run))
    return EXIT_FAILED_TASKS if summary.failed else EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
