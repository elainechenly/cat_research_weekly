"""Settings for the weekly cat-paper digest. Edit the lists here."""
import os

# PubMed journal abbreviations (same list as the original project)
JOURNALS = [
    "J Feline Med Surg", "J Vet Intern Med", "Vet Surg",
    "Vet J", "Vet Res", "Front Vet Sci", "Am J Vet Res", "Annu Rev Anim Biosci",
    "Anim Nutr", "J Anim Sci Biotechnol", "Anim Health Res Rev",
    "J Anim Physiol Anim Nutr (Berl)", "Anim Front",
    "Appl Anim Behav Sci", "J Vet Behav", "Vet Microbiol",
    "J Anim Sci", "J Dairy Sci", "Poult Sci", "Animals (Basel)",
    "Prev Vet Med", "Transbound Emerg Dis",
]

KEYWORDS = [
    "cat", "cats", "felis catus", "felis silvestris catus",
    "feline", "felines", "felid", "felidae", "housecat", "kitten",
]

MATCH_ALL = False    # False = any keyword (OR)
SUBSTRING = False    # False = whole words only ("cat", not "category")
ADD_PLURALS = True   # also search keyword + "s" in the PubMed query
DATE_TYPE = "pdat"   # "pdat" = publication date, "edat" = date added to PubMed

# Optional NCBI details (the email only identifies your requests; it is never used to send mail)
NCBI_EMAIL = os.environ.get("NCBI_EMAIL", "")
NCBI_API_KEY = os.environ.get("NCBI_API_KEY", "")
MAX_RECORDS = 1000

# --- LLM (free tier of the Gemini API) ---
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")  # copy the current Flash-Lite ID from AI Studio
SUMMARY_BATCH = 3     # abstracts per request (saves free daily quota)
SUMMARY_PAUSE = 15    # seconds between requests (stays under per-minute limits)

MANDARIN_SCRIPT = "Simplified Chinese (简体中文)"   # or "Traditional Chinese (繁體中文)"
RETRY_ROUNDS = 1      # extra passes for papers the LLM could not check (e.g. Gemini overloaded)
RETRY_PAUSE = 60      # seconds to wait before an extra pass

# --- Output and email ---
OUTPUT_DIR = "data"                 # weekly CSV files and the email preview are written here
EMAIL_INCLUDE_MANDARIN = True       # False = English-only email (the CSV always has both languages)
SEND_IF_EMPTY = True                # True = still send a short "quiet week" email when nothing was found
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
# Secrets are read from environment variables (GitHub secrets / Colab secrets):
#   GMAIL_USER, GMAIL_APP_PASSWORD, EMAIL_RECIPIENTS (comma, semicolon or newline separated)

# --- Weekly schedule (used by --scheduled; GitHub cron only knows UTC, so the code checks the Pacific weekday) ---
SEND_TZ = "America/Los_Angeles"
SEND_WEEKDAY = 1          # Monday = 0, Tuesday = 1. A scheduled run sends only on this weekday (Pacific time).
