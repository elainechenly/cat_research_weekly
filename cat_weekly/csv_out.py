"""Step 3: keep ONE master CSV with every paper found so far (new weeks are added to it).

UTF-8 with BOM so Excel shows Mandarin correctly. Re-running a week never creates duplicates.
"""
import csv
import os
import re

from . import config

MASTER_NAME = "cat_papers_all.csv"
CSV_FIELDS = ["title", "authors", "journal",
              "english_summary", "mandarin_summary", "english_insight", "mandarin_insight",
              "pub_date", "url", "verified"]


def master_path(out_dir=None):
    return os.path.join(out_dir or config.OUTPUT_DIR, MASTER_NAME)


def _key(title):
    return re.sub(r"[^a-z0-9]", "", (title or "").lower())


def _row(paper):
    row = {f: paper.get(f, "") or "" for f in CSV_FIELDS}
    row["verified"] = "Y" if paper.get("llm_status") == "verified" else "N"
    return row


def read_rows(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def update_csv(papers, out_dir=None):
    """Add this week's papers to the master CSV. Returns (path, rows_added, rows_upgraded).

    - A paper already in the file is not added again.
    - If it was verified = N before and is now Y (e.g. Gemini worked on a re-run), the row is upgraded.
    - A verified = Y row is never overwritten by a later N.
    - Rows are kept newest first by publication date.
    """
    path = master_path(out_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rows = {_key(r["title"]): r for r in read_rows(path)}
    added = upgraded = 0
    for p in papers:
        new, k = _row(p), _key(p.get("title"))
        old = rows.get(k)
        if old is None:
            rows[k] = new
            added += 1
        elif old.get("verified") == "N" and new["verified"] == "Y":
            rows[k] = new
            upgraded += 1
    ordered = sorted(rows.values(), key=lambda r: r.get("pub_date", ""), reverse=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore", restval="")
        w.writeheader()
        w.writerows(ordered)
    return path, added, upgraded
