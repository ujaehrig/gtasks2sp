"""Tests for verifying a created task against the request body."""

import pytest

from tasks2sp import VerificationError, verify

BODY: dict[str, object] = {"title": "x", "tagIds": ["t1"], "dueDay": "2026-10-20"}


def test_identical_fields_pass() -> None:
    verify(BODY, {**BODY, "id": "sp-1", "projectId": "INBOX_PROJECT"})


def test_additional_tags_are_accepted() -> None:
    verify(BODY, {**BODY, "tagIds": ["t0", "t1"]})


@pytest.mark.parametrize("tags", [[], ["t2"], None, "t1"])
def test_missing_import_tag_fails(tags: object) -> None:
    with pytest.raises(VerificationError, match="fields: tagIds"):
        verify(BODY, {**BODY, "tagIds": tags})


def test_all_mismatched_fields_are_named() -> None:
    with pytest.raises(VerificationError, match="fields: title, dueDay"):
        verify(BODY, {"tagIds": ["t1"], "title": "y"})
