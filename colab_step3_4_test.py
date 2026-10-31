# ---- Colab cell: live test of the full pipeline (search -> summaries -> CSV -> email preview) ----
# Before running:
#  1) Delete the old cat-weekly folder + zip, upload the NEW cat-weekly.zip to /content.
#  2) Colab Secrets (key icon, Notebook access ON): GEMINI_API_KEY (needed).
#     For the optional send test (SEND_TEST = True) also add GMAIL_USER, GMAIL_APP_PASSWORD and
#     EMAIL_RECIPIENTS (use ONLY your own address for testing).
#     Gmail app password: turn on 2-Step Verification, then https://myaccount.google.com/apppasswords
import os, subprocess, sys, time
SEND_TEST = False          # False = dry run (nothing is emailed). Set True to really send to EMAIL_RECIPIENTS.

t0 = time.time()
if os.path.exists("/content/cat-weekly.zip"):
    subprocess.run(["unzip", "-oq", "/content/cat-weekly.zip", "-d", "/content"])
os.chdir("/content/cat-weekly"); sys.path.insert(0, os.getcwd())

try:                                         # copy Colab secrets into environment variables
    from google.colab import userdata
    for k in ["GEMINI_API_KEY", "GMAIL_USER", "GMAIL_APP_PASSWORD", "EMAIL_RECIPIENTS"]:
        try: os.environ[k] = userdata.get(k)
        except Exception: pass
except ImportError:
    pass

print(subprocess.run([sys.executable, "run_tests.py"], capture_output=True, text=True).stdout[-200:])

for name in [m for m in list(sys.modules) if m.startswith("cat_weekly")]:
    del sys.modules[name]
from cat_weekly import main
res = main.run(dry_run=not SEND_TEST, force=True)
print(f"\n[{time.time()-t0:.0f}s] {len(res['papers'])} papers | sent={res['sent']}")

# Show the email as it will look, and the CSV
from IPython.display import HTML, display
display(HTML(open(res["preview"], encoding="utf-8").read()))
import pandas as pd
display(pd.read_csv(res["csv"]).head(20))
print("Master CSV:", res["csv"], f"(+{res['csv_added']} new rows, {res['csv_upgraded']} upgraded)")
print("Run this cell again: the CSV should report +0 new rows (no duplicates).")
