"""Step 1: find cat papers from last week (Monday-Sunday) in PubMed."""
import re
import xml.etree.ElementTree as ET
from datetime import date, timedelta

import requests

from . import config

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
BATCH_SIZE = 200
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


# ---------- week window ----------
def last_full_week(today=None):
    """Most recent COMPLETED Monday-Sunday week before `today`.

    Run on any day and you get the week that ended the Sunday before this week's Monday.
    """
    today = today or date.today()
    this_monday = today - timedelta(days=today.weekday())
    return this_monday - timedelta(days=7), this_monday - timedelta(days=1)


# ---------- query + keyword check (same logic as the original script) ----------
def build_regexes(keywords, substring):
    out = {}
    for kw in keywords:
        esc = re.escape(kw)
        out[kw] = re.compile(esc if substring else rf"\b{esc}(s|es)?\b", re.IGNORECASE)
    return out


def build_query(keywords, journals, match_all, add_plurals):
    groups = []
    for kw in keywords:
        variants = [kw, kw + "s"] if add_plurals else [kw]
        groups.append("(" + " OR ".join(f'"{v}"[Title/Abstract]' for v in variants) + ")")
    kw_part = (" AND " if match_all else " OR ").join(groups)
    journal_part = " OR ".join(f'"{j}"[Journal]' for j in journals)
    return f"({journal_part}) AND ({kw_part})"


def _common_params():
    p = {}
    if config.NCBI_EMAIL:
        p["email"] = config.NCBI_EMAIL
    if config.NCBI_API_KEY:
        p["api_key"] = config.NCBI_API_KEY
    return p


def search_ids(query, start, end):
    """PubMed IDs whose config.DATE_TYPE date falls between start and end (inclusive)."""
    params = {"db": "pubmed", "term": query, "retmax": config.MAX_RECORDS, "retmode": "json",
              "datetype": config.DATE_TYPE,
              "mindate": start.strftime("%Y/%m/%d"), "maxdate": end.strftime("%Y/%m/%d"),
              **_common_params()}
    # POST, because the query (22 journals x ~20 keywords) is too long for a URL
    r = requests.post(f"{EUTILS}/esearch.fcgi", data=params, timeout=30)
    r.raise_for_status()
    res = r.json()["esearchresult"]
    return res.get("idlist", []), int(res.get("count", 0))


def fetch_records(ids):
    for i in range(0, len(ids), BATCH_SIZE):
        batch = ids[i:i + BATCH_SIZE]
        r = requests.post(f"{EUTILS}/efetch.fcgi",
                          data={"db": "pubmed", "id": ",".join(batch), "retmode": "xml",
                                **_common_params()}, timeout=60)
        r.raise_for_status()
        yield from ET.fromstring(r.content).findall(".//PubmedArticle")


# ---------- parsing (date logic from refine_html.py) ----------
def _text_of(parent, tag):
    el = parent.find(tag)
    return el.text.strip() if el is not None and el.text else ""


def _month_num(value):
    value = (value or "").strip()
    if value.isdigit():
        n = int(value)
        return n if 1 <= n <= 12 else None
    return MONTHS.get(value[:3].lower())


def make_date(year, month, day):
    """Possibly partial date parts -> (sort_key 'YYYY-MM-DD', display string)."""
    if not (year and year.isdigit()):
        return "0000-00-00", ""
    y, m = int(year), _month_num(month)
    d = int(day) if (m and day and day.isdigit()) else None
    sort_key = f"{y:04d}-{m or 1:02d}-{d or 1:02d}"
    shown = f"{y:04d}" + (f"-{m:02d}" if m else "") + (f"-{d:02d}" if d else "")
    return sort_key, shown


def parse_pub_date(art):
    """Online (electronic) date if the record has one, otherwise the journal issue date."""
    el = art.find(".//ArticleDate[@DateType='Electronic']")
    if el is not None:
        key, shown = make_date(_text_of(el, "Year"), _text_of(el, "Month"), _text_of(el, "Day"))
        if shown:
            return key, shown
    el = art.find(".//JournalIssue/PubDate")
    if el is not None:
        year, month, day = _text_of(el, "Year"), _text_of(el, "Month"), _text_of(el, "Day")
        if not year:                                   # e.g. <MedlineDate>2026 Oct-Dec</MedlineDate>
            medline = _text_of(el, "MedlineDate")
            ym = re.search(r"\d{4}", medline)
            if ym:
                year = ym.group(0)
                mm = re.search(r"[A-Za-z]{3}", medline[ym.end():])
                month = mm.group(0) if mm else ""
        key, shown = make_date(year, month, day)
        if shown:
            return key, shown
    return "0000-00-00", ""


def parse_article(art):
    def text(path):
        el = art.find(path)
        return "".join(el.itertext()).strip() if el is not None else ""

    authors = []
    for a in art.findall(".//AuthorList/Author"):
        name = f"{_text_of(a, 'ForeName')} {_text_of(a, 'LastName')}".strip()
        if name:
            authors.append(name)
    doi_el = art.find(".//ArticleId[@IdType='doi']")
    doi = doi_el.text.strip() if doi_el is not None and doi_el.text else ""
    pmid = text(".//MedlineCitation/PMID")
    sort_date, pub_date = parse_pub_date(art)
    return {
        "pub_date": pub_date, "sort_date": sort_date,
        "title": text(".//ArticleTitle"),
        "authors": "; ".join(authors),
        "journal": text(".//Journal/Title"),
        "doi": doi, "pmid": pmid,
        "url": f"https://doi.org/{doi}" if doi else f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "abstract": " ".join("".join(a.itertext()).strip() for a in art.findall(".//AbstractText")),
    }


# ---------- duplicates ----------
def dedupe(papers):
    """Drop repeated records of the same paper (same title); keep the one that has a DOI."""
    best = {}
    for p in papers:
        key = re.sub(r"[^a-z0-9]", "", p["title"].lower())
        if key not in best or (p["doi"] and not best[key]["doi"]):
            best[key] = p
    return list(best.values())


# ---------- main entry for step 1 ----------
def find_cat_papers(start=None, end=None):
    """Search PubMed for the window, strict-check abstracts, return papers newest first."""
    if start is None or end is None:
        start, end = last_full_week()
    regexes = build_regexes(config.KEYWORDS, config.SUBSTRING)
    query = build_query(config.KEYWORDS, config.JOURNALS, config.MATCH_ALL, config.ADD_PLURALS)
    print(f"Query length: {len(query)} characters. Contacting PubMed...", flush=True)
    ids, total = search_ids(query, start, end)
    print(f"Window {start} to {end}: PubMed reports {total} candidates.")
    papers = []
    print(f"Fetching {len(ids)} records...", flush=True)
    for art in fetch_records(ids):
        rec = parse_article(art)
        found = [kw for kw, rx in regexes.items() if rx.search(rec["abstract"])]
        ok = len(found) == len(regexes) if config.MATCH_ALL else bool(found)
        if ok:
            rec["matched_keywords"] = "; ".join(found)
            papers.append(rec)
    papers = dedupe(papers)
    papers.sort(key=lambda r: r["sort_date"], reverse=True)
    print(f"{len(papers)} papers passed the strict keyword check.")
    return papers
