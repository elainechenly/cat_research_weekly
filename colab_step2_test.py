# ---- Colab cell: live test of Steps 1 + 2 (search, then English + Mandarin summary and owner insight) ----
# Before running:
#  1) Upload the NEW cat-weekly.zip to /content (delete the old zip and folder first).
#  2) Colab left sidebar > key icon (Secrets) > add GEMINI_API_KEY with your key
#     (get one at https://aistudio.google.com/app/api-keys) and switch "Notebook access" ON.
#  3) If Gemini complains about the model name, set GEMINI_MODEL below to a current Flash-Lite ID from AI Studio.
import os, subprocess, sys, time, importlib
t0 = time.time()
def log(msg): print(f"[{time.time()-t0:5.1f}s] {msg}", flush=True)

if os.path.exists("/content/cat-weekly.zip"):
    subprocess.run(["unzip", "-oq", "/content/cat-weekly.zip", "-d", "/content"])
os.chdir("/content/cat-weekly")
sys.path.insert(0, os.getcwd())
# os.environ["GEMINI_MODEL"] = "gemini-3.1-flash-lite"      # optional override

# A) All offline tests
print(subprocess.run([sys.executable, "run_tests.py"], capture_output=True, text=True).stdout[-300:])

# B) Live: search last full week, then summarize
for name in [m for m in list(sys.modules) if m.startswith("cat_weekly")]:
    del sys.modules[name]
from cat_weekly import pubmed, summarize
papers = pubmed.find_cat_papers()
log(f"{len(papers)} papers from PubMed; asking Gemini (about {len(papers)//3*15}s of pauses)...")
before = {p["pmid"]: p["title"] for p in papers}
final = summarize.add_summaries(papers)
log(f"{len(final)} papers kept")

dropped = [t for pm, t in before.items() if pm not in {p["pmid"] for p in final}]
print("\nDROPPED as not about cats:")
for t in dropped: print("  -", t)

print("\nKEPT:")
for p in final:
    print(f"\n[{p['llm_status']}] {p['title']}\n  {p['journal']} | {p['url']}")
    print(f"  SUMMARY (EN): {p['english_summary']}\n  SUMMARY (中文): {p['mandarin_summary']}")
    print(f"  INSIGHT (EN): {p['english_insight']}\n  INSIGHT (中文): {p['mandarin_insight']}")
