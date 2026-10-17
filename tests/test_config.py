"""Tests for reading the configuration from the environment."""

from pathlib import Path

import pytest

from tasks2sp import ConfigError, load_config


def test_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    config = load_config({"SP_TOKEN": "t"})

    assert config.token == "t"
    assert config.api == "http://127.0.0.1:3876"
    assert config.import_tag == "gtask"
    assert config.db_path == tmp_path / ".local/share/tasks2sp/import.sqlite"


def test_explicit_values(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    config = load_config(
        {
            "SP_TOKEN": "t",
            "SP_API": "http://localhost:1",
            "SP_IMPORT_TAG": "x",
            "TASKS2SP_DB": "~/r.sqlite",
        }
    )

    assert config.api == "http://localhost:1"
    assert config.import_tag == "x"
    assert config.db_path == tmp_path / "r.sqlite"


@pytest.mark.parametrize("env", [{}, {"SP_TOKEN": ""}, {"SP_TOKEN": "  "}])
def test_token_is_required(env: dict[str, str]) -> None:
    with pytest.raises(ConfigError, match="SP_TOKEN"):
        load_config(env)


def test_empty_optional_values_fall_back_to_defaults() -> None:
    config = load_config({"SP_TOKEN": "t", "SP_API": "", "SP_IMPORT_TAG": ""})

    assert config.api == "http://127.0.0.1:3876"
    assert config.import_tag == "gtask"
