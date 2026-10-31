import os
import tempfile
from datetime import date
from unittest import mock

from cat_weekly import config, emailer, gate, main, pubmed, state, summarize

START, END = date(2026, 10, 19), date(2026, 10, 25)
PAPER = {"title": "Cats", "url": "https://doi.org/1", "journal": "J", "pub_date": "2026-10-21", "pmid": "1",
         "english_summary": "S", "mandarin_summary": "摘", "english_insight": "I", "mandarin_insight": "提",
         "llm_status": "verified"}


def patched(tmp, papers=None, summarized=None):
    papers = [dict(PAPER)] if papers is None else papers
    return [mock.patch.object(config, "OUTPUT_DIR", tmp),
            mock.patch.object(pubmed, "find_cat_papers", return_value=papers),
            mock.patch.object(summarize, "add_summaries", return_value=summarized if summarized is not None else papers),
            mock.patch.object(emailer, "send_email")]


def run_with(patches, **kw):
    started = [p.start() for p in patches]
    try:
        return main.run(**kw), started
    finally:
        for p in patches:
            p.stop()


def test_dry_run_writes_csv_and_preview_but_does_not_send():
    with tempfile.TemporaryDirectory() as d:
        res, mocks = run_with(patched(d), start=START, end=END, dry_run=True)
        assert os.path.exists(res["csv"]) and os.path.exists(res["preview"])
    mocks[3].assert_not_called()
    assert res["sent"] is False


def test_default_window_is_last_full_week():
    with tempfile.TemporaryDirectory() as d:
        res, mocks = run_with(patched(d), dry_run=True, today=date(2026, 10, 27))
    assert (res["start"], res["end"]) == (START, END)
    mocks[1].assert_called_once_with(START, END)


def test_real_run_sends_to_secret_recipients():
    env = {"GMAIL_USER": "me@gmail.com", "GMAIL_APP_PASSWORD": "pw", "EMAIL_RECIPIENTS": "a@x.com b@y.org"}
    with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, env):
        res, mocks = run_with(patched(d), start=START, end=END)
    assert res["sent"] is True
    args = mocks[3].call_args.args
    assert args[3] == ["a@x.com", "b@y.org"] and args[4] == "me@gmail.com"


def test_missing_secrets_raises_clear_error():
    with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {}, clear=True):
        try:
            run_with(patched(d), start=START, end=END)
            assert False
        except RuntimeError as e:
            assert "GMAIL_USER" in str(e)


def test_quiet_week_skips_llm_and_still_sends_by_default():
    env = {"GMAIL_USER": "me@gmail.com", "GMAIL_APP_PASSWORD": "pw", "EMAIL_RECIPIENTS": "a@x.com"}
    with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, env):
        res, mocks = run_with(patched(d, papers=[]), start=START, end=END)
    mocks[2].assert_not_called()                      # no Gemini call when there is nothing to summarize
    assert res["sent"] is True


def test_quiet_week_not_sent_when_disabled():
    with tempfile.TemporaryDirectory() as d, mock.patch.object(config, "SEND_IF_EMPTY", False):
        res, mocks = run_with(patched(d, papers=[]), start=START, end=END)
    assert res["sent"] is False


def test_only_one_of_start_end_is_an_error():
    try:
        main.run(start=START)
        assert False
    except ValueError:
        pass


ENV = {"GMAIL_USER": "me@gmail.com", "GMAIL_APP_PASSWORD": "pw", "EMAIL_RECIPIENTS": "a@x.com"}


def test_successful_send_marks_the_week_as_sent():
    with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, ENV):
        run_with(patched(d), start=START, end=END)
        assert state.last_sent_week(d) == "2026-10-19"


def test_dry_run_does_not_mark_the_week_as_sent():
    with tempfile.TemporaryDirectory() as d:
        run_with(patched(d), start=START, end=END, dry_run=True)
        assert state.last_sent_week(d) is None


def test_already_sent_week_is_skipped_before_any_work():
    with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, ENV):
        state_patch = patched(d)
        state.mark_sent(START, END, d)
        res, mocks = run_with(state_patch, start=START, end=END)
    assert res["skipped"] is True and res["sent"] is False
    mocks[1].assert_not_called()          # no PubMed search
    mocks[2].assert_not_called()          # no Gemini calls
    mocks[3].assert_not_called()          # no email


def test_force_sends_again_even_if_already_sent():
    with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, ENV):
        patches = patched(d)
        state.mark_sent(START, END, d)
        res, mocks = run_with(patches, start=START, end=END, force=True)
    assert res["sent"] is True and mocks[3].call_count == 1


def test_scheduled_flag_skips_outside_the_window():
    with mock.patch.object(gate, "should_run_now", return_value=False), mock.patch.object(main, "run") as r:
        main.main(["--scheduled"])
    r.assert_not_called()


def test_scheduled_flag_runs_inside_the_window():
    with mock.patch.object(gate, "should_run_now", return_value=True), mock.patch.object(main, "run") as r:
        main.main(["--scheduled"])
    r.assert_called_once()
