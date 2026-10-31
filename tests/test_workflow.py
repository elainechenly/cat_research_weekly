from pathlib import Path

WF = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "weekly.yml").read_text(encoding="utf-8")


def test_main_and_backup_crons_on_tuesday_utc():
    assert '- cron: "0 16 * * 2"' in WF and '- cron: "0 22 * * 2"' in WF


def test_scheduled_runs_use_the_pacific_gate():
    assert "--scheduled" in WF


def test_manual_run_defaults_to_dry_run_and_has_force():
    assert "dry_run:" in WF and "default: true" in WF and "force:" in WF


def test_secrets_are_wired_and_none_are_hardcoded():
    for s in ("GEMINI_API_KEY", "GMAIL_USER", "GMAIL_APP_PASSWORD", "EMAIL_RECIPIENTS"):
        assert f"secrets.{s}" in WF
    assert "AIza" not in WF


def test_manual_inputs_are_passed_via_env_not_inlined_in_shell():
    run_block = WF[WF.index("python -m cat_weekly.main"):]
    assert "${{ inputs." not in WF[WF.index("run: |\n          ARGS=()"):WF.index("python -m cat_weekly.main")]


def test_permissions_and_no_overlapping_runs():
    assert "contents: write" in WF and "cancel-in-progress: false" in WF


def test_dry_runs_do_not_commit():
    assert "inputs.dry_run" in WF[WF.index("Commit updated data"):]


def test_subscriber_secrets_and_apps_script_tests_are_wired():
    assert "secrets.SUBSCRIBERS_URL" in WF and "secrets.SUBSCRIBERS_API_KEY" in WF
    assert "node apps_script/test_code.js" in WF and "node docs/test_page.js" in WF
