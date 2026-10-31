"""Remember which week was already emailed, so a second run (or a retry) never sends a duplicate."""
import json
import os
from datetime import datetime, timezone

from . import config


def _path(out_dir=None):
    return os.path.join(out_dir or config.OUTPUT_DIR, "last_sent.json")


def last_sent_week(out_dir=None):
    try:
        with open(_path(out_dir), encoding="utf-8") as f:
            return json.load(f).get("week_start")
    except (OSError, ValueError):
        return None


def mark_sent(start, end, out_dir=None):
    path = _path(out_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"week_start": start.isoformat(), "week_end": end.isoformat(),
                   "sent_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}, f, indent=2)
