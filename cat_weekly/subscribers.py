"""Read the confirmed subscriber list from the Google Sheet (through the Apps Script web app)."""
import os
from urllib.parse import quote

import requests

from . import emailer


def fetch_subscribers(url=None, key=None, get=requests.get):
    """Return [{"email", "unsubscribe_url"}] for confirmed subscribers, or None if the feature is not configured.

    Raises RuntimeError with a clear message on any problem, so a broken list is never mistaken for an empty one.
    """
    url = (url if url is not None else os.environ.get("SUBSCRIBERS_URL", "")).strip()
    key = (key if key is not None else os.environ.get("SUBSCRIBERS_API_KEY", "")).strip()
    if not url:
        return None
    if not key:
        raise RuntimeError("SUBSCRIBERS_URL is set but SUBSCRIBERS_API_KEY is missing.")
    try:
        r = get(url, params={"action": "list", "key": key}, timeout=60)
        r.raise_for_status()
        data = r.json()
    except ValueError:
        raise RuntimeError("The subscriber list was not JSON. Check the web app is deployed with access "
                           "'Anyone' and that the URL ends in /exec.")
    except requests.RequestException as e:
        raise RuntimeError(f"Could not reach the subscriber list: {e}")
    if not isinstance(data, dict) or not data.get("ok"):
        raise RuntimeError(f"The subscriber list was refused ({data.get('error') if isinstance(data, dict) else 'bad reply'}). "
                           "Check SUBSCRIBERS_API_KEY matches the ADMIN_KEY from setup().")
    out, seen = [], set()
    for item in data.get("subscribers", []):
        email = str(item.get("email", "")).strip()
        token = str(item.get("token", "")).strip()
        if not emailer.EMAIL_RE.match(email) or email.lower() in seen or not token:
            continue
        seen.add(email.lower())
        out.append({"email": email, "unsubscribe_url": f"{url}?action=unsubscribe&token={quote(token, safe='')}"})
    return out


def merge_recipients(subscribers, static_emails, fallback_unsubscribe_url=None):
    """Confirmed subscribers first, then extra addresses from the EMAIL_RECIPIENTS secret (no duplicates)."""
    out = list(subscribers or [])
    seen = {r["email"].lower() for r in out}
    for email in static_emails or []:
        if email.lower() not in seen:
            seen.add(email.lower())
            out.append({"email": email, "unsubscribe_url": fallback_unsubscribe_url or None})
    return out
