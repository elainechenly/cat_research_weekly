# Cat Research Weekly

Every Tuesday (Pacific time) this project emails a short digest of **last week's** (Monday to Sunday)
new cat-related veterinary papers from PubMed. Each paper gets a one-sentence summary and a one-sentence,
plain-language tip for cat owners, in **English and Mandarin**. Every paper is also added to one master CSV.

```
PubMed search (last full Mon-Sun week)  ->  Gemini: keep cat papers, write summary + owner tip (EN + 中文)
        ->  data/cat_papers_all.csv (one master file)  ->  HTML email via Gmail  ->  commit CSV to the repo
```

## Files
| Path | Purpose |
|---|---|
| `cat_weekly/pubmed.py` | Step 1: weekly PubMed search, strict keyword check, de-duplication |
| `cat_weekly/summarize.py` | Step 2: Gemini filter + bilingual summaries and insights, with retries |
| `cat_weekly/csv_out.py` | Step 3: master CSV (`data/cat_papers_all.csv`), no duplicates |
| `cat_weekly/emailer.py` | Step 4: HTML + text email, Gmail SMTP |
| `cat_weekly/gate.py`, `state.py` | Tuesday (Pacific time) check, and "already sent this week" memory |
| `cat_weekly/main.py` | Runs everything. `--dry-run`, `--scheduled`, `--force`, `--start/--end` |
| `.github/workflows/weekly.yml` | The weekly GitHub Actions job |
| `tests/`, `run_tests.py` | Offline tests (`python run_tests.py`, or `pytest`) |
| `colab_*.py` | Cells for testing in Google Colab |

## Settings
Edit `cat_weekly/config.py`: journals, keywords, Gemini model, whether the email includes Mandarin
(`EMAIL_INCLUDE_MANDARIN`), whether to send on a quiet week (`SEND_IF_EMPTY`), and the send window.

## GitHub setup
1. Repository **Settings -> Secrets and variables -> Actions -> New repository secret**. Add:
   `GEMINI_API_KEY`, `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `EMAIL_RECIPIENTS` (comma or newline separated).
   Optional: `NCBI_API_KEY`.
2. **Settings -> Actions -> General -> Workflow permissions**: choose *Read and write permissions*.
3. **Actions** tab -> *Weekly cat research digest* -> **Run workflow**. Leave *Dry run* ticked first.
   Open the run and download the `email-preview` artifact to see the email without sending it.
4. Untick *Dry run* for a real send. Tick *Force* to send again for a week already sent.

## Schedule
The workflow starts every Tuesday at 16:00 UTC (always Tuesday in Pacific time, 8 am PST / 9 am PDT) and again at
22:00 UTC as a backup. A scheduled run sends only on Tuesday in Los Angeles, and only once per week: the backup run
does nothing if the first one already sent, but retries if the first one failed.

## Secrets and privacy
Passwords and the recipient list live only in GitHub secrets. Never commit them. The CSV contains only public
paper information and AI-written summaries.

## Disclaimer
Summaries and tips are AI-generated from abstracts and can be wrong. They are not veterinary advice.
Data: PubMed (NCBI E-utilities). Copyright of each paper stays with its authors and publisher.
