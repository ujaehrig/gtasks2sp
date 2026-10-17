"""Smoke test: the script is importable and its entry point runs."""

import runpy

import pytest

import tasks2sp


def test_main_returns_success_exit_code() -> None:
    assert tasks2sp.main([]) == 0


def test_running_as_script_exits_with_main_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", ["tasks2sp.py"])

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path("tasks2sp.py", run_name="__main__")

    assert exit_info.value.code == 0
