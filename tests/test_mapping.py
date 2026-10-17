"""Tests for mapping a Google Task onto a Super Productivity task body."""

from pathlib import Path

import pytest

from tasks2sp import GoogleTask, read_google_tasks, to_sp_task

TAG_ID = "tag-1"
FIXTURE = Path(__file__).parent / "fixtures" / "gog_tasks.json"


def fixture_task(title: str | None) -> GoogleTask:
    tasks = read_google_tasks(FIXTURE.read_text(encoding="utf-8"))
    return next(task for task in tasks if task.get("title") == title)


def test_maps_title_and_tag() -> None:
    body = to_sp_task({"id": "a", "title": "Einkaufen"}, TAG_ID)

    assert body == {"title": "Einkaufen", "tagIds": [TAG_ID]}


@pytest.mark.parametrize("title", [None, "", "   "])
def test_missing_or_blank_title_becomes_placeholder(title: str | None) -> None:
    task: GoogleTask = {"id": "a"}
    if title is not None:
        task["title"] = title

    assert to_sp_task(task, TAG_ID)["title"] == "(ohne Titel)"


def test_fixture_task_without_title_gets_placeholder() -> None:
    body = to_sp_task(fixture_task(None), TAG_ID)

    assert body["title"] == "(ohne Titel)"


def test_due_becomes_date_part_without_timezone_shift() -> None:
    body = to_sp_task(
        {"id": "a", "title": "x", "due": "2026-10-20T00:00:00.000Z"}, TAG_ID
    )

    assert body["dueDay"] == "2026-10-20"


def test_due_in_the_past_is_kept() -> None:
    body = to_sp_task(fixture_task("Offen mit Datum in der Vergangenheit"), TAG_ID)

    assert body["dueDay"] == "2023-12-23"


def test_no_due_means_no_due_day() -> None:
    body = to_sp_task(fixture_task("Offen ohne Datum"), TAG_ID)

    assert "dueDay" not in body


def test_parent_is_ignored() -> None:
    body = to_sp_task(fixture_task("Unteraufgabe"), TAG_ID)

    assert "parentId" not in body
    assert "parent" not in body


def test_notes_and_web_view_link_are_separated_by_blank_line() -> None:
    body = to_sp_task(
        {"id": "a", "title": "x", "notes": "Notiz", "webViewLink": "https://w"},
        TAG_ID,
    )

    assert body["notes"] == "Notiz\n\nhttps://w"


def test_only_web_view_link() -> None:
    body = to_sp_task({"id": "a", "title": "x", "webViewLink": "https://w"}, TAG_ID)

    assert body["notes"] == "https://w"


def test_only_notes() -> None:
    body = to_sp_task({"id": "a", "title": "x", "notes": "Notiz"}, TAG_ID)

    assert body["notes"] == "Notiz"


def test_blank_notes_are_dropped() -> None:
    body = to_sp_task({"id": "a", "title": "x", "notes": "  \n"}, TAG_ID)

    assert "notes" not in body


def test_links_use_description_and_fall_back_to_type() -> None:
    body = to_sp_task(
        {
            "id": "a",
            "title": "x",
            "notes": "Notiz",
            "links": [
                {"type": "email", "description": "Betreff", "link": "https://m"},
                {"type": "keep_note", "link": "https://k"},
                {"type": "email", "description": "", "link": "https://e"},
            ],
            "webViewLink": "https://w",
        },
        TAG_ID,
    )

    assert body["notes"] == (
        "Notiz\n\n"
        "- [Betreff](https://m)\n"
        "- [keep_note](https://k)\n"
        "- [email](https://e)\n\n"
        "https://w"
    )


def test_malformed_links_are_skipped() -> None:
    body = to_sp_task(
        {
            "id": "a",
            "title": "x",
            "links": ["not a dict", {"type": "email"}, {"link": "https://l"}],
        },
        TAG_ID,
    )

    assert body["notes"] == "- [link](https://l)"


def test_links_that_are_not_a_list_are_ignored() -> None:
    body = to_sp_task({"id": "a", "title": "x", "links": "oops"}, TAG_ID)

    assert "notes" not in body


def test_fixture_task_with_mail_link() -> None:
    body = to_sp_task(fixture_task("Offen mit Mail-Link"), TAG_ID)

    assert body == {
        "title": "Offen mit Mail-Link",
        "tagIds": [TAG_ID],
        "dueDay": "2026-10-18",
        "notes": (
            "- [Betreff einer Mail](https://mail.google.com/mail/#all/example)"
            "\n\nhttps://tasks.google.com/task/web0004?sa=6"
        ),
    }
