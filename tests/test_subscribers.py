from unittest import mock

import requests

from cat_weekly import subscribers

URL = "https://script.google.com/macros/s/ABC/exec"


def reply(payload=None, status=200, json_error=False):
    r = mock.Mock(status_code=status)
    r.raise_for_status.side_effect = None if status < 400 else requests.HTTPError(f"{status}")
    if json_error:
        r.json.side_effect = ValueError("not json")
    else:
        r.json.return_value = payload
    return r


def test_not_configured_returns_none():
    assert subscribers.fetch_subscribers(url="", key="") is None


def test_url_without_key_is_an_error():
    try:
        subscribers.fetch_subscribers(url=URL, key="")
        assert False
    except RuntimeError as e:
        assert "SUBSCRIBERS_API_KEY" in str(e)


def test_returns_personal_unsubscribe_links_and_sends_the_key():
    get = mock.Mock(return_value=reply({"ok": True, "subscribers": [
        {"email": "a@x.com", "token": "tok1"}, {"email": "b@y.org", "token": "tok 2/&"}]}))
    out = subscribers.fetch_subscribers(url=URL, key="SECRET", get=get)
    assert out[0] == {"email": "a@x.com", "unsubscribe_url": URL + "?action=unsubscribe&token=tok1"}
    assert out[1]["unsubscribe_url"].endswith("token=tok%202%2F%26")        # token is URL-encoded
    assert get.call_args.kwargs["params"] == {"action": "list", "key": "SECRET"}


def test_invalid_duplicate_or_tokenless_rows_are_skipped():
    get = mock.Mock(return_value=reply({"ok": True, "subscribers": [
        {"email": "good@x.com", "token": "t"}, {"email": "GOOD@x.com", "token": "t2"},
        {"email": "not-an-email", "token": "t"}, {"email": "notoken@x.com", "token": ""}]}))
    assert [r["email"] for r in subscribers.fetch_subscribers(url=URL, key="k", get=get)] == ["good@x.com"]


def test_empty_list_is_valid_and_distinct_from_a_failure():
    get = mock.Mock(return_value=reply({"ok": True, "subscribers": []}))
    assert subscribers.fetch_subscribers(url=URL, key="k", get=get) == []


def test_wrong_key_is_reported_clearly():
    get = mock.Mock(return_value=reply({"ok": False, "error": "unauthorized"}))
    try:
        subscribers.fetch_subscribers(url=URL, key="bad", get=get)
        assert False
    except RuntimeError as e:
        assert "unauthorized" in str(e) and "ADMIN_KEY" in str(e)


def test_html_instead_of_json_gives_a_helpful_message():
    get = mock.Mock(return_value=reply(json_error=True))
    try:
        subscribers.fetch_subscribers(url=URL, key="k", get=get)
        assert False
    except RuntimeError as e:
        assert "Anyone" in str(e) and "/exec" in str(e)


def test_network_and_http_errors_become_runtime_errors():
    for get in (mock.Mock(side_effect=requests.ConnectionError("down")), mock.Mock(return_value=reply(status=500))):
        try:
            subscribers.fetch_subscribers(url=URL, key="k", get=get)
            assert False
        except RuntimeError as e:
            assert "Could not reach" in str(e)


def test_merge_keeps_subscribers_first_and_drops_duplicates_case_insensitively():
    subs = [{"email": "S@x.com", "unsubscribe_url": "u"}]
    out = subscribers.merge_recipients(subs, ["s@x.com", "a@x.com"], "https://page")
    assert out == [{"email": "S@x.com", "unsubscribe_url": "u"},
                   {"email": "a@x.com", "unsubscribe_url": "https://page"}]
    assert subscribers.merge_recipients(None, [], None) == []
