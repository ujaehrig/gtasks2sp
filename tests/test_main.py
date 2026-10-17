"""End-to-end tests of ``main`` against the fake API."""

import io
import json
import sqlite3
from pathlib import Path

import pytest
from conftest import GTASK_TAG_ID, TOKEN, FakeSp

from tasks2sp import EXIT_FAILED_TASKS, EXIT_OK, EXIT_PRECHECK, main

GOG_OUTPUT = (Path(__file__).parent / "fixtures" / "gog_tasks.json").read_text("utf-8")
OPEN_IDS = {
    task["id"] for task in json.loads(GOG_OUTPUT) if task["status"] == "needsAction"
}


class Runner:
    """Runs ``main`` with a controlled environment, stdin and env file."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
        fake: FakeSp,
    ) -> None:
        self.monkeypatch = monkeypatch
        self.capsys = capsys
        self.db = tmp_path / "db" / "import.sqlite"
        # an empty env file keeps the developer's real .env out of the tests
        self.env_file = tmp_path / "empty.env"
        self.env_file.write_text("")
        monkeypatch.setenv("SP_TOKEN", TOKEN)
        monkeypatch.setenv("SP_API", fake.base_url)
        monkeypatch.setenv("SP_IMPORT_TAG", "gtask")
        monkeypatch.setenv("TASKS2SP_DB", str(self.db))
        self.stderr = ""

    def __call__(self, *args: str, stdin: str = GOG_OUTPUT) -> int:
        self.monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
        code = main(["--env-file", str(self.env_file), *args])
        self.stderr = self.capsys.readouterr().err
        return code

    def registered(self) -> set[str]:
        if not self.db.exists():
            return set()
        with sqlite3.connect(self.db) as connection:
            rows = connection.execute("SELECT google_task_id FROM imported").fetchall()
        connection.close()
        return {row[0] for row in rows}


@pytest.fixture
def run(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    fake_sp: FakeSp,
) -> Runner:
    return Runner(monkeypatch, capsys, tmp_path, fake_sp)


def test_first_run_imports_all_open_tasks(run: Runner, fake_sp: FakeSp) -> None:
    assert run() == EXIT_OK

    assert run.registered() == OPEN_IDS
    bodies = fake_sp.post_bodies()
    assert len(bodies) == 6
    assert all(body["tagIds"] == [GTASK_TAG_ID] for body in bodies)
    assert "Erledigt" not in [body.get("title") for body in bodies]
    assert "imported: Offen mit Notiz -> sp-" in run.stderr
    assert "7 read, 6 open, 6 imported, 0 already imported, 0 failed" in run.stderr


def test_second_run_imports_nothing(run: Runner, fake_sp: FakeSp) -> None:
    run()
    fake_sp.requests.clear()

    assert run() == EXIT_OK

    assert fake_sp.posts() == []
    assert "already imported: Offen ohne Datum" in run.stderr
    assert "0 imported, 6 already imported, 0 failed" in run.stderr


def test_failed_task_is_not_registered_and_retried(
    run: Runner, fake_sp: FakeSp
) -> None:
    fake_sp.fail_post_titles = {"Offen mit Notiz"}

    assert run() == EXIT_FAILED_TASKS

    assert len(run.registered()) == 5
    assert "FAILED: Offen mit Notiz: INVALID_TASK: rejected by fake" in run.stderr
    assert "5 imported, 0 already imported, 1 failed" in run.stderr

    fake_sp.fail_post_titles = set()
    assert run() == EXIT_OK
    assert run.registered() == OPEN_IDS
    assert "1 imported, 5 already imported, 0 failed" in run.stderr


def test_discarded_field_fails_verification(run: Runner, fake_sp: FakeSp) -> None:
    fake_sp.drop_on_read = {"dueDay"}

    assert run() == EXIT_FAILED_TASKS

    # two open tasks in the fixture have no due date and pass verification
    assert len(run.registered()) == 2
    assert "verification failed for fields: dueDay" in run.stderr


def test_dry_run_writes_nothing(run: Runner, fake_sp: FakeSp) -> None:
    assert run("--dry-run") == EXIT_OK

    assert fake_sp.posts() == []
    assert not run.db.exists()
    assert "would import: Offen mit Notiz" in run.stderr
    assert "6 would be imported, 0 already imported" in run.stderr


def test_dry_run_respects_existing_register(run: Runner, fake_sp: FakeSp) -> None:
    fake_sp.fail_post_titles = {"Offen mit Notiz"}
    run()
    fake_sp.requests.clear()

    assert run("--dry-run") == EXIT_OK

    assert fake_sp.posts() == []
    assert "would import: Offen mit Notiz" in run.stderr
    assert "1 would be imported, 5 already imported" in run.stderr


def test_precheck_failure_creates_nothing(run: Runner, fake_sp: FakeSp) -> None:
    fake_sp.tags = []

    assert run() == EXIT_PRECHECK

    assert fake_sp.posts() == []
    assert not run.db.exists()
    assert "error: import tag 'gtask' does not exist" in run.stderr


def test_wrong_token(
    run: Runner, fake_sp: FakeSp, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SP_TOKEN", "wrong")

    assert run() == EXIT_PRECHECK

    assert fake_sp.posts() == []
    assert "wrong" not in run.stderr
    assert "Access Token" in run.stderr


def test_unreachable_api(
    run: Runner, monkeypatch: pytest.MonkeyPatch, unused_url: str
) -> None:
    monkeypatch.setenv("SP_API", unused_url)

    assert run() == EXIT_PRECHECK

    assert "cannot reach Super Productivity" in run.stderr


def test_invalid_input_is_rejected_before_contacting_the_api(
    run: Runner, fake_sp: FakeSp
) -> None:
    assert run(stdin="nope") == EXIT_PRECHECK

    assert fake_sp.requests == []
    assert "error: input is not valid JSON" in run.stderr


def test_missing_token(run: Runner, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SP_TOKEN")

    assert run() == EXIT_PRECHECK

    assert "error: SP_TOKEN is not set" in run.stderr


def test_env_file_is_loaded_but_environment_wins(
    run: Runner, fake_sp: FakeSp, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SP_TOKEN")
    run.env_file.write_text(f"SP_TOKEN={TOKEN}\nSP_IMPORT_TAG=other\n")

    assert run() == EXIT_OK

    # SP_IMPORT_TAG=gtask from the environment beats "other" from the file
    assert all(body["tagIds"] == [GTASK_TAG_ID] for body in fake_sp.post_bodies())
