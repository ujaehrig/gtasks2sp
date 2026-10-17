"""Smoke test: the file runs as a script."""

import runpy

import pytest


def test_running_as_script_exits_with_main_result(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["tasks2sp.py", "--help"])

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path("tasks2sp.py", run_name="__main__")

    assert exit_info.value.code == 0
    assert "--dry-run" in capsys.readouterr().out
