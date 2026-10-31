# ---- Colab cell: live test of Step 1 ----
# Upload cat-weekly.zip to /content first. Output prints as it goes, with timings.
import os, subprocess, sys, time, importlib, traceback
t0 = time.time()
def log(msg): print(f"[{time.time()-t0:5.1f}s] {msg}", flush=True)

if os.path.exists("/content/cat-weekly.zip"):
    subprocess.run(["unzip", "-oq", "/content/cat-weekly.zip", "-d", "/content"])
os.chdir("/content/cat-weekly")
sys.path.insert(0, os.getcwd())
log("Folder ready (requests is already installed in Colab; no pip needed).")

# A) Offline unit tests, run in-process (no pytest needed)
for name in [m for m in list(sys.modules) if m.startswith(("cat_weekly", "tests"))]:
    del sys.modules[name]
tests = importlib.import_module("tests.test_pubmed")
ok = bad = 0
for n in sorted(dir(tests)):
    if n.startswith("test_"):
        try: getattr(tests, n)(); ok += 1
        except Exception: bad += 1; print("FAIL", n); traceback.print_exc()
log(f"Unit tests: {ok} passed, {bad} failed")

# B) Live PubMed search for the last full Monday-Sunday week
from cat_weekly import pubmed
start, end = pubmed.last_full_week()
log(f"Searching {start} ({start:%A}) to {end} ({end:%A})")
papers = pubmed.find_cat_papers(start, end)
log(f"Done: {len(papers)} papers")
for p in papers:
    print(f"[{p['pub_date']}] {p['title']}\n    {p['journal']} | {p['url']}")

# C) Optional wider window if last week is quiet:
# from datetime import timedelta
# papers = pubmed.find_cat_papers(start - timedelta(days=28), end)
