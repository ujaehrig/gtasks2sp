"""Tests for the precheck that runs before any task is created."""

import pytest
from conftest import GTASK_TAG_ID, TOKEN, FakeSp

from tasks2sp import PrecheckError, SpClient, precheck


def run(fake: FakeSp, tag: str = "gtask") -> str:
    return precheck(SpClient(fake.base_url, TOKEN), tag)


def test_returns_id_of_import_tag(fake_sp: FakeSp) -> None:
    assert run(fake_sp) == GTASK_TAG_ID


def test_tag_name_is_case_insensitive(fake_sp: FakeSp) -> None:
    assert run(fake_sp, "GTask") == GTASK_TAG_ID


def test_server_not_up(fake_sp: FakeSp) -> None:
    fake_sp.health = {"server": "down", "rendererReady": True}

    with pytest.raises(PrecheckError, match="not ready"):
        run(fake_sp)


def test_renderer_not_ready(fake_sp: FakeSp) -> None:
    fake_sp.health = {"server": "up", "rendererReady": False}

    with pytest.raises(PrecheckError, match="not ready"):
        run(fake_sp)


def test_missing_tag_lists_available_tags(fake_sp: FakeSp) -> None:
    with pytest.raises(PrecheckError, match=r"'nope' does not exist.*gtask, other"):
        run(fake_sp, "nope")


def test_ambiguous_tag(fake_sp: FakeSp) -> None:
    fake_sp.tags.append({"id": "tag-2", "title": "GTASK", "taskIds": []})

    with pytest.raises(PrecheckError, match="ambiguous"):
        run(fake_sp)


@pytest.mark.parametrize("name", ["Today", "today"])
def test_today_is_rejected_without_asking_the_api(fake_sp: FakeSp, name: str) -> None:
    with pytest.raises(PrecheckError, match="Today"):
        run(fake_sp, name)

    assert fake_sp.requests == []


def test_tag_with_today_id_is_rejected(fake_sp: FakeSp) -> None:
    fake_sp.tags = [{"id": "TODAY", "title": "Heute", "taskIds": []}]

    with pytest.raises(PrecheckError, match="Today"):
        run(fake_sp, "Heute")
