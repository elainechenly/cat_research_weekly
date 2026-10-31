import email
from datetime import date
from unittest import mock

from cat_weekly import emailer

START, END = date(2026, 10, 19), date(2026, 10, 25)


def verified(title="Cats and CKD", url="https://doi.org/10.1/a"):
    return {"title": title, "url": url, "journal": "J Feline Med Surg", "pub_date": "2026-10-21",
            "english_summary": "EN summary.", "mandarin_summary": "中文摘要。",
            "english_insight": "EN insight.", "mandarin_insight": "中文提示。", "llm_status": "verified"}


def unchecked(title="Unchecked paper", url="https://pubmed.ncbi.nlm.nih.gov/9/"):
    return {"title": title, "url": url, "journal": "Vet J", "pub_date": "2026-10-22",
            "english_summary": "", "mandarin_summary": "", "english_insight": "", "mandarin_insight": "",
            "llm_status": "unchecked"}


def test_subject_has_week_range():
    subject, _, _ = emailer.build_email([verified()], START, END)
    assert subject == "Weekly cat research: Oct 19 to Oct 25, 2026"


def test_subject_across_years():
    subject, _, _ = emailer.build_email([], date(2026, 12, 28), date(2027, 1, 3))
    assert "Dec 28, 2026 to Jan 3, 2027" in subject


def test_both_languages_in_html_and_text_by_default():
    _, h, t = emailer.build_email([verified()], START, END)
    for s in ("EN summary.", "中文摘要。", "EN insight.", "中文提示。", "https://doi.org/10.1/a"):
        assert s in h and s in t


def test_english_only_option_removes_mandarin():
    _, h, t = emailer.build_email([verified()], START, END, include_mandarin=False)
    assert "中文" not in h and "中文" not in t and "对您" not in h and "EN insight." in h


def test_additional_reading_section_only_for_unchecked_and_at_bottom():
    _, h, t = emailer.build_email([verified(), unchecked()], START, END)
    assert "Additional Reading" in h and h.index("Cats and CKD") < h.index("Additional Reading") < h.index("Unchecked paper")
    assert "ADDITIONAL READING" in t
    # unchecked paper must not get a summary card
    assert h.count("What this means for you:") == 1


def test_no_additional_reading_when_all_verified():
    _, h, t = emailer.build_email([verified()], START, END)
    assert "Additional Reading" not in h and "ADDITIONAL READING" not in t


def test_quiet_week_message():
    _, h, t = emailer.build_email([], START, END)
    assert "No new cat papers" in h and "No new cat papers" in t


def test_html_is_escaped():
    p = verified(title='<script>alert(1)</script> & "cats"')
    _, h, _ = emailer.build_email([p], START, END)
    assert "<script>" not in h and "&lt;script&gt;" in h


def test_new_notice_english_and_chinese():
    _, h, t = emailer.build_email([verified()], START, END)
    for s in ("Disclaimer &amp; Copyright Notice", "do not constitute veterinary or medical advice",
              "Sources &amp; Copyright:", "does not imply endorsement by PubMed", "cat’s individual health needs",
              "免责声明与版权声明", "不构成兽医或医疗建议", "不代表 PubMed、论文作者或出版商的认可或背书"):
        assert s in h, s
    assert h.index("Disclaimer &amp; Copyright Notice") < h.index("免责声明与版权声明")
    assert "Disclaimer & Copyright Notice" in t and "免责声明与版权声明" in t and "不构成兽医或医疗建议" in t


def test_notice_english_only_when_mandarin_off():
    _, h, t = emailer.build_email([verified()], START, END, include_mandarin=False)
    assert "do not constitute veterinary or medical advice" in h and "免责声明" not in h and "免责声明" not in t


def test_notice_is_last_thing_in_the_email():
    _, h, _ = emailer.build_email([verified(), unchecked()], START, END)
    assert h.index("Additional Reading") < h.index("Disclaimer &amp; Copyright Notice")


def test_parse_recipients():
    assert emailer.parse_recipients("a@x.com, b@y.org;c@z.net\nA@X.com") == ["a@x.com", "b@y.org", "c@z.net"]
    assert emailer.parse_recipients("") == []
    try:
        emailer.parse_recipients("good@x.com, not-an-email")
        assert False
    except ValueError as e:
        assert "not-an-email" in str(e)


def test_send_uses_bcc_style_envelope_and_keeps_chinese():
    smtp = mock.MagicMock()
    factory = mock.MagicMock(return_value=smtp)
    smtp.__enter__.return_value = smtp
    subject, h, t = emailer.build_email([verified()], START, END)
    msg = emailer.send_email(subject, h, t, ["a@x.com", "b@y.org"], "me@gmail.com", "pw", smtp_factory=factory)
    smtp.login.assert_called_once_with("me@gmail.com", "pw")
    kwargs = smtp.send_message.call_args.kwargs
    assert kwargs["to_addrs"] == ["a@x.com", "b@y.org"] and kwargs["from_addr"] == "me@gmail.com"
    headers = str(msg["To"]) + str(msg["Cc"] or "") + str(msg["Bcc"] or "")
    assert "a@x.com" not in headers and "b@y.org" not in headers      # recipients stay private
    parsed = email.message_from_bytes(msg.as_bytes())
    html_part = [p for p in parsed.walk() if p.get_content_type() == "text/html"][0]
    assert "中文摘要" in html_part.get_payload(decode=True).decode("utf-8")
    assert {p.get_content_type() for p in parsed.walk()} >= {"text/plain", "text/html"}


def test_send_requires_recipients():
    try:
        emailer.send_email("s", "h", "t", [], "me@gmail.com", "pw")
        assert False
    except ValueError:
        pass
