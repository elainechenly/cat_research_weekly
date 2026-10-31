"""Step 2: drop papers not about cats; add one-sentence English + Mandarin summaries and
one-sentence, grandma-simple owner insights in both languages (Gemini free tier)."""
import json
import os
import re
import time

import requests

from . import config

NOT_CAT = "not about cat"
FIELDS = ("english_summary", "mandarin_summary", "english_insight", "mandarin_insight")


def get_gemini_key():
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        try:                                   # Colab "Secrets" panel (key icon on the left)
            from google.colab import userdata
            key = userdata.get("GEMINI_API_KEY")
        except Exception:
            key = ""
    return key or ""


def call_gemini(prompt, key, retries=4):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent"
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}}
    last = None
    for attempt in range(retries):
        r = requests.post(url, headers={"x-goog-api-key": key}, json=body, timeout=90)
        if r.status_code in (429, 500, 503):   # rate limit or Gemini overloaded: wait and retry
            last = r.status_code
            wait = 15 * (attempt + 1)
            print(f"  Gemini returned {last}; waiting {wait}s...", flush=True)
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    kind = "rate limit / daily free quota" if last == 429 else "Gemini overloaded or unavailable"
    raise RuntimeError(f"Gave up after {retries} tries (last status {last}: {kind}).")


def build_prompt(batch):
    items = [{"pmid": r["pmid"], "title": r["title"], "abstract": r["abstract"]} for r in batch]
    return (
        "You help ordinary cat owners understand new veterinary research. "
        "For each paper write FOUR things, each in exactly ONE plain sentence:\n"
        "1. 'english_summary': what was studied and the main finding (at most 35 words).\n"
        "2. 'mandarin_summary': the same summary in " + config.MANDARIN_SCRIPT + " (at most 70 characters).\n"
        "3. 'english_insight': how a cat owner can use this knowledge, in very simple everyday words that a "
        "grandmother with no science background would understand (at most 35 words). Speak to the owner "
        "(for example 'This study can help you...'). Avoid jargon and abbreviations unless you explain them.\n"
        "4. 'mandarin_insight': the same insight in plain, everyday " + config.MANDARIN_SCRIPT + " "
        "that an elderly person would understand (at most 70 characters).\n"
        "Use ONLY what the abstract supports: never invent advice, doses, or promises. If the finding is "
        "early or lab-based, say honestly that it may help vets in the future, and suggest asking your vet "
        "when it concerns health.\n"
        "If the paper is NOT mainly about cats (felines), set ALL FOUR fields to 'not about cat'.\n"
        'Return ONLY a JSON array like [{"pmid": "...", "english_summary": "...", "mandarin_summary": "...", '
        '"english_insight": "...", "mandarin_insight": "..."}], '
        "one object per paper, using the same pmid values.\n\n" + json.dumps(items, ensure_ascii=False)
    )


def parse_json(text):
    """Parse the model's reply, tolerating ```json fences."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return json.loads(text)


def _mark_unchecked(r):
    for f in FIELDS:
        r[f] = ""
    r["llm_status"] = "unchecked"


def _run_batches(papers, key, llm):
    """One pass over `papers`. Returns papers to keep (verified or unchecked); not-cat ones are dropped."""
    kept = []
    n = config.SUMMARY_BATCH
    for i in range(0, len(papers), n):
        batch = papers[i:i + n]
        try:
            result = parse_json(llm(build_prompt(batch), key))
            by_pmid = {str(x.get("pmid")): x for x in result}
            for r in batch:
                x = by_pmid.get(r["pmid"])
                if x is None:
                    _mark_unchecked(r)
                    kept.append(r)
                    continue
                vals = {f: str(x.get(f, "")).strip() for f in FIELDS}
                if any(v.lower().startswith(NOT_CAT) for v in vals.values()):
                    continue                                   # not about cats: drop
                if all(vals.values()):
                    r.update(vals)
                    r["llm_status"] = "verified"
                else:
                    _mark_unchecked(r)
                kept.append(r)
        except Exception as e:
            print(f"  Batch starting at paper {i + 1} failed: {e}", flush=True)
            for r in batch:
                _mark_unchecked(r)
                kept.append(r)
        if i + n < len(papers):
            time.sleep(config.SUMMARY_PAUSE)
    return kept


def add_summaries(papers, key=None, llm=call_gemini):
    """Return papers about cats with summaries + insights (English and Mandarin) and llm_status.

    - Papers the model says are not about cats are removed.
    - Papers that could not be checked are KEPT, marked 'unchecked', and retried
      for config.RETRY_ROUNDS extra passes.
    """
    key = get_gemini_key() if key is None else key
    if not key:
        print("No Gemini API key found; keeping all papers as 'unchecked'.")
        for r in papers:
            _mark_unchecked(r)
        return papers

    kept = _run_batches(papers, key, llm)
    for _ in range(config.RETRY_ROUNDS):
        pending = [p for p in kept if p["llm_status"] == "unchecked"]
        if not pending:
            break
        print(f"Retrying {len(pending)} unchecked papers after {config.RETRY_PAUSE}s...", flush=True)
        time.sleep(config.RETRY_PAUSE)
        redone = _run_batches(pending, key, llm)
        kept = [p for p in kept if p["llm_status"] == "verified"] + redone
    kept.sort(key=lambda p: p.get("sort_date", ""), reverse=True)
    return kept
