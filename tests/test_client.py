"""Tests for the Super Productivity REST client."""

import pytest
from conftest import GTASK_TAG_ID, TOKEN, FakeSp

from tasks2sp import ApiError, AuthError, SpClient, UnreachableError


def client(fake: FakeSp, token: str = TOKEN) -> SpClient:
    return SpClient(fake.base_url, token)


def test_health(fake_sp: FakeSp) -> None:
    assert client(fake_sp).health() == {"server": "up", "rendererReady": True}


def test_sends_bearer_token(fake_sp: FakeSp) -> None:
    client(fake_sp).health()

    assert fake_sp.requests[0].authorization == f"Bearer {TOKEN}"


def test_trailing_slash_in_base_url_is_ignored(fake_sp: FakeSp) -> None:
    SpClient(fake_sp.base_url + "/", TOKEN).health()

    assert fake_sp.requests[0].path == "/health"


def test_tags(fake_sp: FakeSp) -> None:
    tags = client(fake_sp).tags()

    assert [tag["title"] for tag in tags] == ["Today", "gtask", "other"]


def test_create_and_get_task(fake_sp: FakeSp) -> None:
    sp = client(fake_sp)
    body: dict[str, object] = {"title": "x", "tagIds": [GTASK_TAG_ID]}

    created = sp.create_task(body)
    fetched = sp.get_task(str(created["id"]))

    assert fake_sp.posts()[0].body == body
    assert fetched["title"] == "x"
    assert fetched["tagIds"] == [GTASK_TAG_ID]
    assert fetched["projectId"] == "INBOX_PROJECT"


def test_wrong_token_raises_auth_error_without_leaking_token(
    fake_sp: FakeSp,
) -> None:
    with pytest.raises(AuthError) as error_info:
        client(fake_sp, token="secret-value").tags()

    assert "secret-value" not in str(error_info.value)
    assert "Access Token" in str(error_info.value)


def test_api_error_carries_code_and_message(fake_sp: FakeSp) -> None:
    with pytest.raises(ApiError) as error_info:
        client(fake_sp).get_task("missing")

    assert error_info.value.code == "TASK_NOT_FOUND"
    assert str(error_info.value) == "TASK_NOT_FOUND: Task not found"


def test_error_response_without_details(fake_sp: FakeSp) -> None:
    fake_sp.raw_response = (500, b'{"ok": false}')

    with pytest.raises(ApiError, match="HTTP_500: request failed"):
        client(fake_sp).health()


def test_non_json_response(fake_sp: FakeSp) -> None:
    fake_sp.raw_response = (200, b"<html>")

    with pytest.raises(ApiError, match="INVALID_RESPONSE"):
        client(fake_sp).health()


def test_non_json_error_response(fake_sp: FakeSp) -> None:
    fake_sp.raw_response = (502, b"Bad Gateway")

    with pytest.raises(ApiError, match="INVALID_RESPONSE: HTTP 502"):
        client(fake_sp).health()


def test_ok_false_with_success_status(fake_sp: FakeSp) -> None:
    fake_sp.raw_response = (
        200,
        b'{"ok": false, "error": {"code": "X", "message": "y"}}',
    )

    with pytest.raises(ApiError, match="X: y"):
        client(fake_sp).health()


def test_data_of_wrong_shape(fake_sp: FakeSp) -> None:
    fake_sp.raw_response = (200, b'{"ok": true, "data": []}')

    with pytest.raises(ApiError, match="expected a JSON object"):
        client(fake_sp).health()


def test_tags_of_wrong_shape(fake_sp: FakeSp) -> None:
    fake_sp.raw_response = (200, b'{"ok": true, "data": [1]}')

    with pytest.raises(ApiError, match="expected a list of JSON objects"):
        client(fake_sp).tags()


def test_unreachable_server(unused_url: str) -> None:
    with pytest.raises(UnreachableError, match="Enable local REST API"):
        SpClient(unused_url, TOKEN).health()
