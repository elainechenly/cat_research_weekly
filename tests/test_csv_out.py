import csv
import tempfile

from cat_weekly import csv_out


def paper(title, date="2026-10-21", status="verified", summ="S"):
    return {"title": title, "authors": "A; B", "journal": "J Feline Med Surg", "pub_date": date,
            "english_summary": summ, "mandarin_summary": "猫的摘要" if summ else "",
            "english_insight": "I" if summ else "", "mandarin_insight": "猫的提示" if summ else "",
            "url": "https://doi.org/10.1/" + title[:3], "llm_status": status,
            "abstract": "internal, not a column", "pmid": "1", "sort_date": "x"}


def rows(path):
    return list(csv.DictReader(open(path, encoding="utf-8-sig", newline="")))


def test_exact_columns_and_yn_flag_no_internal_fields():
    with tempfile.TemporaryDirectory() as d:
        path, added, up = csv_out.update_csv([paper("Cats A"), paper("Cats B", status="unchecked", summ="")], out_dir=d)
        r = rows(path)
    assert list(r[0].keys()) == ["title", "authors", "journal", "english_summary", "mandarin_summary",
                                 "english_insight", "mandarin_insight", "pub_date", "url", "verified"]
    assert {x["title"]: x["verified"] for x in r} == {"Cats A": "Y", "Cats B": "N"}
    assert (added, up) == (2, 0)


def test_new_week_is_appended_to_previous_rows():
    with tempfile.TemporaryDirectory() as d:
        csv_out.update_csv([paper("Week one paper", "2026-10-21")], out_dir=d)
        path, added, _ = csv_out.update_csv([paper("Week two paper", "2026-10-28")], out_dir=d)
        r = rows(path)
    assert added == 1 and [x["title"] for x in r] == ["Week two paper", "Week one paper"]   # newest first


def test_rerunning_same_week_adds_no_duplicates():
    with tempfile.TemporaryDirectory() as d:
        csv_out.update_csv([paper("Same paper")], out_dir=d)
        path, added, up = csv_out.update_csv([paper("same  paper.")], out_dir=d)      # same title, different punctuation
        assert len(rows(path)) == 1 and (added, up) == (0, 0)


def test_unchecked_row_is_upgraded_when_later_verified():
    with tempfile.TemporaryDirectory() as d:
        csv_out.update_csv([paper("Paper X", status="unchecked", summ="")], out_dir=d)
        path, added, up = csv_out.update_csv([paper("Paper X", summ="Real summary")], out_dir=d)
        r = rows(path)
    assert (added, up) == (0, 1) and r[0]["verified"] == "Y" and r[0]["english_summary"] == "Real summary"


def test_verified_row_is_never_downgraded():
    with tempfile.TemporaryDirectory() as d:
        csv_out.update_csv([paper("Paper Y", summ="Good")], out_dir=d)
        path, _, up = csv_out.update_csv([paper("Paper Y", status="unchecked", summ="")], out_dir=d)
        r = rows(path)
    assert up == 0 and r[0]["verified"] == "Y" and r[0]["english_summary"] == "Good"


def test_quiet_week_keeps_existing_rows_and_creates_header_if_new():
    with tempfile.TemporaryDirectory() as d:
        path, added, _ = csv_out.update_csv([], out_dir=d)
        assert added == 0 and open(path, encoding="utf-8-sig").read().startswith("title,authors")
        csv_out.update_csv([paper("Keep me")], out_dir=d)
        csv_out.update_csv([], out_dir=d)
        assert [x["title"] for x in rows(path)] == ["Keep me"]


def test_bom_mandarin_commas_quotes_roundtrip():
    p = paper('Cats, "quoted" title')
    with tempfile.TemporaryDirectory() as d:
        path, _, _ = csv_out.update_csv([p], out_dir=d)
        assert open(path, "rb").read().startswith(b"\xef\xbb\xbf")
        r = rows(path)
    assert r[0]["mandarin_summary"] == "猫的摘要" and r[0]["title"] == p["title"]
