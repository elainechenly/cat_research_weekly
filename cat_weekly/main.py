"""Run the whole weekly pipeline: search -> summarize -> CSV -> email.

  python -m cat_weekly.main --dry-run                 # do everything except send; writes an email preview
  python -m cat_weekly.main                           # real run (needs the email secrets)
  python -m cat_weekly.main --start 2026-10-19 --end 2026-10-25   # a specific week
  python -m cat_weekly.main --scheduled               # for GitHub Actions: only runs on Tuesday (Pacific time)
  python -m cat_weekly.main --force                   # send even if this week was already sent
"""
import argparse
import os
import sys
from datetime import date

from . import config, csv_out, emailer, gate, pubmed, state, summarize


def run(start=None, end=None, dry_run=False, today=None, force=False):
    if (start is None) != (end is None):
        raise ValueError("Give both start and end, or neither.")
    if start is None:
        start, end = pubmed.last_full_week(today)

    if not dry_run and not force and state.last_sent_week() == start.isoformat():
        print(f"Week {start} to {end} was already sent. Nothing to do (use --force to send again).")
        return {"start": start, "end": end, "papers": [], "sent": False, "skipped": True}

    papers = pubmed.find_cat_papers(start, end)
    papers = summarize.add_summaries(papers) if papers else []
    csv_path, added, upgraded = csv_out.update_csv(papers)
    subject, html_body, text_body = emailer.build_email(papers, start, end)

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    preview = os.path.join(config.OUTPUT_DIR, "email_preview.html")
    with open(preview, "w", encoding="utf-8") as f:
        f.write(html_body)
    result = {"start": start, "end": end, "papers": papers, "csv": csv_path,
              "preview": preview, "subject": subject, "sent": False,
              "csv_added": added, "csv_upgraded": upgraded}
    print(f"Master CSV: {csv_path} (+{added} new, {upgraded} upgraded)\nEmail preview: {preview}\nSubject: {subject}", flush=True)

    if dry_run:
        print("Dry run: email not sent.")
        return result
    if not papers and not config.SEND_IF_EMPTY:
        print("No papers and SEND_IF_EMPTY is off: email not sent.")
        return result

    user = os.environ.get("GMAIL_USER", "")
    password = os.environ.get("GMAIL_APP_PASSWORD", "")
    recipients = emailer.parse_recipients(os.environ.get("EMAIL_RECIPIENTS", ""))
    if not (user and password and recipients):
        raise RuntimeError("Missing GMAIL_USER, GMAIL_APP_PASSWORD or EMAIL_RECIPIENTS.")
    emailer.send_email(subject, html_body, text_body, recipients, user, password)
    state.mark_sent(start, end)
    result["sent"] = True
    print(f"Email sent to {len(recipients)} recipient(s).")
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="do everything except send the email")
    ap.add_argument("--scheduled", action="store_true",
                    help="only run on Tuesday, Pacific time (for the weekly GitHub workflow)")
    ap.add_argument("--force", action="store_true", help="send even if this week was already sent")
    ap.add_argument("--start", type=date.fromisoformat, help="YYYY-MM-DD (use with --end)")
    ap.add_argument("--end", type=date.fromisoformat, help="YYYY-MM-DD (use with --start)")
    a = ap.parse_args(argv)
    if a.scheduled and not gate.should_run_now():
        print("It is not Tuesday in Pacific time; skipping this scheduled run.")
        return
    try:
        run(a.start, a.end, a.dry_run, force=a.force)
    except (ValueError, RuntimeError) as e:
        sys.exit(f"Error: {e}")


if __name__ == "__main__":
    main()
