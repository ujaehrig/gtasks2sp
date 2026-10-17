"""Tests for reading the configuration from the environment."""

from pathlib import Path

import pytest

from tasks2sp import ConfigError, default_env_file, load_config


def test_default_env_file_follows_symlink_to_script(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    script = project / "tasks2sp.py"
    script.write_text("")
    link_dir = tmp_path / "bin"
    link_dir.mkdir()
    link = link_dir / "tasks2sp.py"
    link.symlink_to(script)

    assert default_env_file(link) == project / ".env"


def test_default_env_file_is_next_to_this_script() -> None:
    expected = Path(__file__).resolve().parent.parent / ".env"

    assert default_env_file() == expected


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
