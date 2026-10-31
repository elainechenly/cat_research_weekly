import tempfile
from datetime import date, datetime, timedelta, timezone

from cat_weekly import gate, state


def utc(y, m, d, h, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=timezone.utc)


def test_any_time_on_a_summer_tuesday_runs():
    # Tue Oct 27 2026 is PDT (UTC-7): Tuesday runs from 07:00 UTC to 06:59 UTC Wednesday
    for h in (7, 12, 16, 22, 23):
        assert gate.should_run_now(utc(2026, 10, 27, h)) is True
    assert gate.should_run_now(utc(2026, 10, 28, 6, 59)) is True      # 11:59pm Tuesday PDT
    assert gate.should_run_now(utc(2026, 10, 28, 7, 0)) is False      # midnight: Wednesday
    assert gate.should_run_now(utc(2026, 10, 27, 6, 59)) is False     # 11:59pm Monday PDT


def test_any_time_on_a_winter_tuesday_runs():
    # Tue Nov 3 2026 is PST (UTC-8): Tuesday runs from 08:00 UTC to 07:59 UTC Wednesday
    assert gate.should_run_now(utc(2026, 11, 3, 8, 0)) is True
    assert gate.should_run_now(utc(2026, 11, 4, 7, 59)) is True
    assert gate.should_run_now(utc(2026, 11, 3, 7, 59)) is False
    assert gate.should_run_now(utc(2026, 11, 4, 8, 0)) is False


def test_both_workflow_cron_times_are_tuesday_pacific_all_year():
    d = date(2026, 1, 6)                                              # a Tuesday
    while d.year == 2026:
        for hour in (16, 22):                                         # the two cron times in weekly.yml
            assert gate.should_run_now(utc(d.year, d.month, d.day, hour)) is True, (d, hour)
        d += timedelta(days=7)


def test_other_weekdays_never_run_at_the_cron_times():
    d = date(2026, 1, 1)
    while d.year == 2026:
        if d.weekday() != 1:                                          # not UTC-Tuesday
            for hour in (16, 22):
                assert gate.should_run_now(utc(d.year, d.month, d.day, hour)) is False, (d, hour)
        d += timedelta(days=1)


def test_naive_datetime_treated_as_utc():
    assert gate.should_run_now(datetime(2026, 10, 27, 16)) is True


def test_state_roundtrip_and_missing_file():
    with tempfile.TemporaryDirectory() as d:
        assert state.last_sent_week(d) is None
        state.mark_sent(date(2026, 10, 19), date(2026, 10, 25), d)
        assert state.last_sent_week(d) == "2026-10-19"


def test_corrupt_state_file_is_ignored():
    with tempfile.TemporaryDirectory() as d:
        open(d + "/last_sent.json", "w").write("{not json")
        assert state.last_sent_week(d) is None
