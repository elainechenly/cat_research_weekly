import json
from unittest import mock

from cat_weekly import config, summarize


def paper(pmid, title="T"):
    return {"pmid": pmid, "title": title, "abstract": "abstract " + pmid, "sort_date": "2026-10-2" + pmid[-1:]}


def fake_llm_factory(answers):
    """answers: pmid -> (summary, insight). Mandarin versions are faked. Records the calls made."""
    calls = []

    def llm(prompt, key):
        calls.append(prompt)
        pmids = [p["pmid"] for p in json.loads(prompt.split("\n\n")[-1])]   # paper list is the last block
        return json.dumps([{"pmid": p,
                            "english_summary": answers[p][0], "mandarin_summary": "中文:" + answers[p][0],
                            "english_insight": answers[p][1], "mandarin_insight": "中文:" + answers[p][1]}
                           for p in pmids if p in answers])
    llm.calls = calls
    return llm


def run(papers, llm, key="k"):
    with mock.patch.object(config, "SUMMARY_PAUSE", 0), mock.patch.object(config, "RETRY_PAUSE", 0), \
         mock.patch.object(summarize.time, "sleep"):
        return summarize.add_summaries(papers, key=key, llm=llm)


def test_verified_papers_get_all_four_fields():
    llm = fake_llm_factory({"1": ("Cats with CKD were studied.", "This can help you care for a cat.")})
    out = run([paper("1")], llm)[0]
    assert out["llm_status"] == "verified"
    assert out["english_summary"].startswith("Cats") and "help you" in out["english_insight"]
    assert out["mandarin_summary"].startswith("中文") and out["mandarin_insight"].startswith("中文")


def test_not_about_cat_is_dropped():
    llm = fake_llm_factory({"1": ("Cats sleep.", "Let them nap."), "2": ("not about cat", "not about cat")})
    out = run([paper("1"), paper("2")], llm)
    assert [p["pmid"] for p in out] == ["1"]


def test_missing_pmid_in_reply_is_kept_unchecked():
    llm = fake_llm_factory({"1": ("S", "I")})
    out = run([paper("1"), paper("2")], llm)
    assert {p["pmid"]: p["llm_status"] for p in out} == {"1": "verified", "2": "unchecked"}


def test_failed_batch_keeps_papers_unchecked():
    def boom(prompt, key):
        raise RuntimeError("overloaded")
    out = run([paper("1"), paper("2")], boom)
    assert [p["llm_status"] for p in out] == ["unchecked", "unchecked"]
    assert all(p[f] == "" for p in out for f in summarize.FIELDS)


def test_retry_pass_recovers_papers_after_a_failed_first_try():
    good = fake_llm_factory({"1": ("S", "I")})
    state = {"n": 0}

    def flaky(prompt, key):
        state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError("503")
        return good(prompt, key)
    out = run([paper("1")], flaky)
    assert out[0]["llm_status"] == "verified" and state["n"] == 2


def test_retry_pass_can_drop_a_not_cat_paper_that_was_unchecked():
    state = {"n": 0}
    good = fake_llm_factory({"1": ("not about cat", "not about cat")})

    def flaky(prompt, key):
        state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError("503")
        return good(prompt, key)
    assert run([paper("1")], flaky) == []


def test_no_retry_when_everything_verified():
    llm = fake_llm_factory({"1": ("S", "I")})
    run([paper("1")], llm)
    assert len(llm.calls) == 1


def test_no_key_keeps_everything_unchecked():
    with mock.patch.object(summarize, "get_gemini_key", return_value=""):
        out = summarize.add_summaries([paper("1")], key=None)
    assert out[0]["llm_status"] == "unchecked"


def test_batching_makes_one_call_per_batch():
    llm = fake_llm_factory({str(i): ("S", "I") for i in range(7)})
    with mock.patch.object(config, "SUMMARY_BATCH", 3):
        out = run([paper(str(i)) for i in range(7)], llm)
    assert len(llm.calls) == 3 and len(out) == 7          # 3 + 3 + 1


def test_missing_mandarin_is_unchecked_not_verified():
    def llm(prompt, key):
        return json.dumps([{"pmid": "1", "english_summary": "S", "mandarin_summary": "",
                            "english_insight": "I", "mandarin_insight": "中"}])
    assert run([paper("1")], llm)[0]["llm_status"] == "unchecked"


def test_parse_json_handles_code_fences():
    assert summarize.parse_json('```json\n[{"a": 1}]\n```') == [{"a": 1}]
    assert summarize.parse_json('[{"a": 1}]') == [{"a": 1}]


def test_prompt_asks_for_both_languages_and_grandma_simple():
    p = summarize.build_prompt([paper("1")])
    for f in summarize.FIELDS:
        assert f in p
    assert "grandmother" in p and "Simplified Chinese" in p and "ALL FOUR" in p


def test_call_gemini_retries_on_503_then_succeeds():
    bad, good = mock.Mock(status_code=503), mock.Mock(status_code=200)
    good.json.return_value = {"candidates": [{"content": {"parts": [{"text": "[]"}]}}]}
    with mock.patch("requests.post", side_effect=[bad, good]), mock.patch.object(summarize.time, "sleep"):
        assert summarize.call_gemini("p", "k") == "[]"


def test_call_gemini_error_message_names_overload_not_quota():
    bad = mock.Mock(status_code=503)
    with mock.patch("requests.post", return_value=bad), mock.patch.object(summarize.time, "sleep"):
        try:
            summarize.call_gemini("p", "k", retries=2)
            assert False
        except RuntimeError as e:
            assert "overloaded" in str(e) and "quota" not in str(e)
