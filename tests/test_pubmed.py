import xml.etree.ElementTree as ET
from datetime import date
from unittest import mock

from cat_weekly import config, pubmed

SAMPLE = """<PubmedArticle><MedlineCitation><PMID>111</PMID><Article>
<Journal><Title>J Feline Med Surg</Title><JournalIssue><PubDate><Year>2026</Year><Month>Oct</Month></PubDate></JournalIssue></Journal>
<ArticleTitle>Chronic kidney disease in <i>cats</i></ArticleTitle>
<Abstract><AbstractText>We studied cats with CKD.</AbstractText></Abstract>
<AuthorList><Author><LastName>Smith</LastName><ForeName>Ann</ForeName></Author></AuthorList>
<ArticleDate DateType="Electronic"><Year>2026</Year><Month>10</Month><Day>21</Day></ArticleDate>
</Article></MedlineCitation>
<PubmedData><ArticleIdList><ArticleId IdType="doi">10.1/abc</ArticleId></ArticleIdList></PubmedData></PubmedArticle>"""


def test_last_full_week_from_every_weekday():
    # Mon Oct 19 - Sun Oct 25, 2026 is "last week" for any day from Mon Oct 26 to Sun Nov 1
    for d in range(26, 32):
        assert pubmed.last_full_week(date(2026, 10, d)) == (date(2026, 10, 19), date(2026, 10, 25))
    assert pubmed.last_full_week(date(2026, 11, 1)) == (date(2026, 10, 19), date(2026, 10, 25))


def test_last_full_week_tuesday_and_year_boundary():
    assert pubmed.last_full_week(date(2026, 10, 27)) == (date(2026, 10, 19), date(2026, 10, 25))
    assert pubmed.last_full_week(date(2027, 1, 5)) == (date(2026, 12, 28), date(2027, 1, 3))


def test_window_is_monday_to_sunday():
    s, e = pubmed.last_full_week(date(2026, 10, 30))
    assert s.weekday() == 0 and e.weekday() == 6 and (e - s).days == 6


def test_whole_word_match():
    rx = pubmed.build_regexes(["cat"], substring=False)["cat"]
    assert rx.search("Cats were studied") and rx.search("a cat")
    assert not rx.search("the category of")


def test_query_shape():
    q = pubmed.build_query(["cat"], ["Vet J"], False, True)
    assert q == '("Vet J"[Journal]) AND (("cat"[Title/Abstract] OR "cats"[Title/Abstract]))'


def test_parse_article():
    rec = pubmed.parse_article(ET.fromstring(SAMPLE))
    assert rec["pub_date"] == "2026-10-21"
    assert rec["title"] == "Chronic kidney disease in cats"
    assert rec["url"] == "https://doi.org/10.1/abc" and rec["authors"] == "Ann Smith"


def test_partial_dates():
    assert pubmed.make_date("2026", "Oct", "") == ("2026-10-01", "2026-10")
    assert pubmed.make_date("2026", "", "") == ("2026-01-01", "2026")
    assert pubmed.make_date("", "", "") == ("0000-00-00", "")


def test_search_sends_exact_dates():
    fake = mock.Mock()
    fake.json.return_value = {"esearchresult": {"idlist": ["1"], "count": "1"}}
    with mock.patch("requests.post", return_value=fake) as g:
        ids, total = pubmed.search_ids("q", date(2026, 10, 19), date(2026, 10, 25))
    p = g.call_args.kwargs["data"]
    assert p["mindate"] == "2026/10/19" and p["maxdate"] == "2026/10/25"
    assert p["datetype"] == config.DATE_TYPE and "reldate" not in p
    assert ids == ["1"] and total == 1


def test_find_cat_papers_filters_non_cat():
    other = (SAMPLE.replace("We studied cats with CKD.", "A study of category effects.")
                   .replace("<PMID>111", "<PMID>222"))
    arts = [ET.fromstring(SAMPLE), ET.fromstring(other)]
    with mock.patch.object(pubmed, "search_ids", return_value=(["111", "222"], 2)), \
         mock.patch.object(pubmed, "fetch_records", return_value=iter(arts)):
        papers = pubmed.find_cat_papers(date(2026, 10, 19), date(2026, 10, 25))
    assert [p["pmid"] for p in papers] == ["111"]


def test_dedupe_keeps_doi_version():
    a = {"title": "Propofol in Cats.", "doi": "", "pmid": "2"}
    b = {"title": "propofol in cats", "doi": "10.1/x", "pmid": "1"}
    c = {"title": "Something else", "doi": "", "pmid": "3"}
    out = pubmed.dedupe([a, b, c])
    assert [p["pmid"] for p in out] == ["1", "3"]
