"""A fake Super Productivity REST API for tests.

The responses are built from real API responses stored in ``fixtures/``, so
the tests exercise the shapes the app actually sends.
"""

import json
import socket
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
TOKEN = "test-token"
GTASK_TAG_ID = "tag-gtask"


def load_fixture(name: str) -> dict[str, object]:
    """Load one of the recorded JSON responses."""
    return cast(dict[str, object], json.loads((FIXTURES / name).read_text("utf-8")))


@dataclass
class Request:
    """A request the fake server received."""

    method: str
    path: str
    authorization: str | None
    body: object


@dataclass
class FakeSp:
    """State and behaviour switches of the fake API, adjustable per test."""

    base_url: str = ""
    health: dict[str, object] = field(
        default_factory=lambda: {"server": "up", "rendererReady": True}
    )
    tags: list[dict[str, object]] = field(
        default_factory=lambda: [
            {"id": "TODAY", "title": "Today", "taskIds": []},
            {"id": GTASK_TAG_ID, "title": "gtask", "taskIds": []},
            {"id": "tag-other", "title": "other", "taskIds": []},
        ]
    )
    tasks: dict[str, dict[str, object]] = field(
        default_factory=dict[str, dict[str, object]]
    )
    requests: list[Request] = field(default_factory=list[Request])
    fail_post_titles: set[str] = field(default_factory=set[str])
    """Titles for which ``POST /tasks`` answers with an API error."""
    drop_on_read: set[str] = field(default_factory=set[str])
    """Fields that ``GET /tasks/<id>`` omits, simulating a discarded field."""
    raw_response: tuple[int, bytes] | None = None
    """When set, every request is answered with this status and raw body."""

    def posts(self) -> list[Request]:
        """Return all ``POST /tasks`` requests."""
        return [r for r in self.requests if r.method == "POST"]

    def post_bodies(self) -> list[dict[str, object]]:
        """Return the JSON bodies of all ``POST /tasks`` requests."""
        return [cast(dict[str, object], r.body) for r in self.posts()]


def _handler(fake: FakeSp) -> type[BaseHTTPRequestHandler]:
    template = cast(
        dict[str, object], load_fixture("sp_post_task_response.json")["data"]
    )

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            del format, args  # keep test output quiet

        def _send(self, status: int, payload: object) -> None:
            self._send_raw(status, json.dumps(payload).encode())

        def _send_raw(self, status: int, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _handle(self, method: str) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            body: object = json.loads(raw) if raw else None
            authorization = self.headers.get("Authorization")
            fake.requests.append(Request(method, self.path, authorization, body))
            if fake.raw_response is not None:
                self._send_raw(*fake.raw_response)
                return
            if authorization != f"Bearer {TOKEN}":
                self._send(401, load_fixture("sp_unauthorized_response.json"))
                return
            self._route(method, body)

        def _route(self, method: str, body: object) -> None:
            if method == "GET" and self.path == "/health":
                self._send(200, {"ok": True, "data": fake.health})
            elif method == "GET" and self.path == "/tags":
                self._send(200, {"ok": True, "data": fake.tags})
            elif method == "POST" and self.path == "/tasks":
                self._create(cast(dict[str, object], body))
            elif method == "GET" and self.path.startswith("/tasks/"):
                task = fake.tasks.get(self.path.removeprefix("/tasks/"))
                if task is None:
                    self._send(404, load_fixture("sp_not_found_response.json"))
                    return
                shown = {k: v for k, v in task.items() if k not in fake.drop_on_read}
                self._send(200, {"ok": True, "data": shown})
            else:
                self._send(404, {"ok": False, "error": {"code": "NOT_FOUND"}})

        def _create(self, body: dict[str, object]) -> None:
            if body.get("title") in fake.fail_post_titles:
                error = {"code": "INVALID_TASK", "message": "rejected by fake"}
                self._send(400, {"ok": False, "error": error})
                return
            task_id = f"sp-{len(fake.tasks) + 1}"
            task = {**template, "notes": None, "dueDay": None, **body, "id": task_id}
            task = {k: v for k, v in task.items() if v is not None}
            fake.tasks[task_id] = task
            self._send(201, {"ok": True, "data": task})

        def do_GET(self) -> None:
            self._handle("GET")

        def do_POST(self) -> None:
            self._handle("POST")

    return Handler


@pytest.fixture
def fake_sp() -> Iterator[FakeSp]:
    """Run a fake Super Productivity API on a random local port."""
    fake = FakeSp()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(fake))
    fake.base_url = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    yield fake
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture
def unused_url() -> str:
    """Return a local URL on which nothing listens."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}"
