# ---- Colab cell: send ONE sample email to yourself (no PubMed, no Gemini). Tests email delivery only. ----
# Colab Secrets needed (key icon on the left, Notebook access ON):
#   GMAIL_USER          your Gmail address, e.g. you@gmail.com
#   GMAIL_APP_PASSWORD  the 16-letter app password (NOT your normal password; spaces are fine, we remove them)
#   EMAIL_RECIPIENTS    where to send the test: use ONLY your own address first
import os, subprocess, sys
from datetime import date

if os.path.exists("/content/cat-weekly.zip"):
    subprocess.run(["unzip", "-oq", "/content/cat-weekly.zip", "-d", "/content"])
os.chdir("/content/cat-weekly"); sys.path.insert(0, os.getcwd())
from google.colab import userdata
for k in ["GMAIL_USER", "GMAIL_APP_PASSWORD", "EMAIL_RECIPIENTS"]:
    os.environ[k] = userdata.get(k)                     # raises a clear error if the secret is missing

for name in [m for m in list(sys.modules) if m.startswith("cat_weekly")]:
    del sys.modules[name]
from cat_weekly import emailer

verified = {"title": "EXPRESS: Mineral Analysis of Feline Treats: Unrecognized Sources of Phosphorus and Calcium in the Management of Chronic Kidney Disease.",
 "url": "https://doi.org/10.1177/1098612X261500321", "journal": "Journal of feline medicine and surgery", "pub_date": "2026-10-21",
 "english_summary": "This study analyzed phosphorus and calcium levels in various cat purée treats and found that mineral content varies significantly, which is important for cats managing chronic kidney disease.",
 "mandarin_summary": "研究分析了多种猫用肉泥零食，发现其中的磷和钙含量差异巨大，这对患有慢性肾病的猫非常重要。",
 "english_insight": "If your cat has kidney disease, check with your vet before giving treats, as some contain high levels of phosphorus that could affect your cat's health.",
 "mandarin_insight": "如果您的猫患有肾病，给零食前请先咨询兽医，因为有些零食含磷量高，可能会影响猫的健康。", "llm_status": "verified"}
unchecked = {"title": "Example paper the AI could not check this week", "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
 "journal": "Veterinary journal", "pub_date": "2026-10-22", "llm_status": "unchecked"}

subject, html_body, text_body = emailer.build_email([verified, unchecked], date(2026, 10, 19), date(2026, 10, 25))
recipients = emailer.parse_recipients(os.environ["EMAIL_RECIPIENTS"])
emailer.send_email("[TEST] " + subject, html_body, text_body, recipients,
                   os.environ["GMAIL_USER"].strip(), os.environ["GMAIL_APP_PASSWORD"].replace(" ", ""))
print(f"Sent to {recipients}. Check the inbox, then Spam/Promotions if you don't see it within a minute.")
