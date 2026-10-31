"""Step 4: build the weekly email (HTML + plain text) and send it through Gmail SMTP."""
import html
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, formatdate

from . import config

EMAIL_RE = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")
NOTICE_TITLE_EN = "Disclaimer & Copyright Notice"
NOTICE_EN = [
    ("Disclaimer:", "The summaries, insights, and practical tips provided in this digest are AI-generated based on "
     "the abstracts of the referenced research papers. They are intended for informational and educational "
     "purposes only and may contain inaccuracies, omissions, or misinterpretations. They do not constitute "
     "veterinary or medical advice, diagnosis, or treatment recommendations. Always consult a licensed "
     "veterinarian regarding your cat’s individual health needs, and do not delay or disregard professional "
     "advice based on this digest. Readers are encouraged to consult the original publications for the full "
     "study details, methodology, findings, and limitations."),
    ("Sources & Copyright:", "Bibliographic information and links are provided for reference and further reading. "
     "PubMed serves as a bibliographic and literature-discovery source for the referenced publications; the "
     "original articles may be hosted by their respective publishers or repositories. Copyright and other "
     "applicable intellectual property rights in the original publications remain with their respective rights "
     "holders. This digest is an independently prepared summary and does not imply endorsement by PubMed, the "
     "authors, or the publishers."),
]
NOTICE_TITLE_ZH = "免责声明与版权声明"
NOTICE_ZH = [
    ("免责声明：", "本周报中的论文摘要、研究要点及实用建议均由人工智能（AI）根据相关研究论文的摘要生成，仅供信息参考与学术交流使用，"
     "可能存在不准确、遗漏或解读偏差。本周报不构成兽医或医疗建议、诊断或治疗方案。有关您家猫咪的具体健康状况，"
     "请咨询持有合法执业资格的兽医；请勿仅依据本周报延误就医或忽视专业建议。建议读者查阅原始论文，"
     "以了解完整的研究背景、方法、结果及研究局限性。"),
    ("来源与版权：", "本周报提供相关文献的书目信息及链接，供读者查阅和进一步阅读。PubMed 是文献检索与书目信息服务平台，"
     "相关论文的全文可能由各自的出版商或文献存储平台提供。原始论文的版权及其他适用的知识产权仍归其各自的权利人所有。"
     "本周报为独立编制的研究摘要，不代表 PubMed、论文作者或出版商的认可或背书。"),
]


def _notice_block(paras, title="", lang=""):
    attr = f' lang="{lang}"' if lang else ""
    out = [f'<div{attr} style="margin-top:14px">']
    if title:
        out.append(f'<div style="font-size:13px;font-weight:700;color:#4a5568">{esc(title)}</div>')
    out += [f'<p style="font-size:12px;line-height:1.5;color:#718096;margin:6px 0">'
            f'<strong>{esc(label)}</strong> {esc(text)}</p>' for label, text in paras]
    return "".join(out) + "</div>"


def _notice_html(zh):
    out = ['<div style="margin-top:28px;padding-top:12px;border-top:1px solid #e2e8f0">',
           f'<div style="font-size:15px;font-weight:700;color:#2d3748">{esc(NOTICE_TITLE_EN)}</div>',
           '<div style="font-size:11px;letter-spacing:.5px;text-transform:uppercase;color:#a0aec0;margin-top:8px">'
           'English</div>',
           _notice_block(NOTICE_EN)]
    if zh:
        out.append(_notice_block(NOTICE_ZH, title=NOTICE_TITLE_ZH, lang="zh"))
    return "".join(out) + "</div>"


def _notice_text(zh):
    lines = ["", NOTICE_TITLE_EN, "English"]
    lines += [f"{label} {text}" for label, text in NOTICE_EN]
    if zh:
        lines += ["", NOTICE_TITLE_ZH]
        lines += [f"{label} {text}" for label, text in NOTICE_ZH]
    return lines


def esc(s):
    return html.escape(s or "", quote=True)


def parse_recipients(text):
    """Split on commas, semicolons, spaces or newlines; validate; de-duplicate (keeps order)."""
    parts = [p for p in re.split(r"[,;\s]+", text or "") if p]
    bad = [p for p in parts if not EMAIL_RE.match(p)]
    if bad:
        raise ValueError(f"Invalid email address(es): {', '.join(bad)}")
    seen, out = set(), []
    for p in parts:
        if p.lower() not in seen:
            seen.add(p.lower())
            out.append(p)
    return out


def _range_label(start, end):
    if start.year == end.year:
        return f"{start:%b} {start.day} to {end:%b} {end.day}, {end.year}"
    return f"{start:%b} {start.day}, {start.year} to {end:%b} {end.day}, {end.year}"


def _split(papers):
    verified = [p for p in papers if p.get("llm_status") == "verified"]
    extra = [p for p in papers if p.get("llm_status") != "verified"]
    return verified, extra


def _card(p, zh):
    meta = " &middot; ".join(x for x in [esc(p.get("journal")), esc(p.get("pub_date"))] if x)
    parts = [f'<div style="background:#fff;border-radius:8px;padding:16px 18px;margin:0 0 16px 0;'
             f'border:1px solid #e2e8f0">',
             f'<a href="{esc(p["url"])}" style="font-size:17px;font-weight:600;color:#2b6cb0;'
             f'text-decoration:none">{esc(p["title"])}</a>',
             f'<div style="font-size:13px;color:#718096;margin:4px 0 10px 0">{meta}</div>',
             f'<div style="font-size:15px;color:#2d3748;margin-bottom:8px"><strong>Summary:</strong> '
             f'{esc(p["english_summary"])}</div>']
    if zh:
        parts.append(f'<div lang="zh" style="font-size:15px;color:#2d3748;margin-bottom:10px">'
                     f'<strong>摘要：</strong>{esc(p["mandarin_summary"])}</div>')
    parts.append(f'<div style="background:#fffaf0;border-left:4px solid #ed8936;padding:8px 12px;'
                 f'font-size:15px;color:#7b341e"><strong>What this means for you:</strong> '
                 f'{esc(p["english_insight"])}')
    if zh:
        parts.append(f'<div lang="zh" style="margin-top:6px"><strong>对您有什么用：</strong>'
                     f'{esc(p["mandarin_insight"])}</div>')
    parts.append("</div></div>")
    return "".join(parts)


def build_email(papers, start, end, include_mandarin=None):
    """Return (subject, html_body, text_body). Verified papers first, unchecked ones under 'Additional Reading'."""
    zh = config.EMAIL_INCLUDE_MANDARIN if include_mandarin is None else include_mandarin
    verified, extra = _split(papers)
    label = _range_label(start, end)
    subject = f"Weekly cat research: {label}"
    count = f"{len(verified)} new paper{'s' if len(verified) != 1 else ''}"

    h = [f'<html><body style="margin:0;padding:16px;background:#f4f6f9;font-family:-apple-system,'
         f'BlinkMacSystemFont,\'Segoe UI\',Roboto,\'PingFang SC\',\'Microsoft YaHei\',Arial,sans-serif">'
         f'<div style="max-width:640px;margin:0 auto">',
         f'<h1 style="font-size:22px;color:#1a365d;margin:0 0 4px 0">Weekly Cat Research</h1>',
         f'<div style="font-size:14px;color:#555;margin-bottom:18px">{esc(label)} &middot; {count}</div>']
    t = [f"WEEKLY CAT RESEARCH - {label}", count, ""]

    if not papers:
        h.append('<p style="font-size:15px;color:#2d3748">No new cat papers were found in the tracked '
                 'journals last week. See you next Tuesday!</p>')
        t.append("No new cat papers were found in the tracked journals last week.")
    for p in verified:
        h.append(_card(p, zh))
        t += [p["title"], f'{p.get("journal", "")} | {p.get("pub_date", "")}', f'Summary: {p["english_summary"]}']
        if zh:
            t.append(f'摘要：{p["mandarin_summary"]}')
        t.append(f'What this means for you: {p["english_insight"]}')
        if zh:
            t.append(f'对您有什么用：{p["mandarin_insight"]}')
        t += [p["url"], ""]

    if extra:
        h.append('<h2 style="font-size:17px;color:#2d3748;margin:24px 0 4px 0">Additional Reading</h2>'
                 '<div style="font-size:13px;color:#718096;margin-bottom:8px">New papers that our AI helper '
                 'could not check or summarize this week.</div><ul style="padding-left:20px;margin:0">')
        t += ["ADDITIONAL READING (not checked or summarized by AI this week)"]
        for p in extra:
            meta = " &middot; ".join(x for x in [esc(p.get("journal")), esc(p.get("pub_date"))] if x)
            h.append(f'<li style="margin-bottom:8px;font-size:14px"><a href="{esc(p["url"])}" '
                     f'style="color:#2b6cb0">{esc(p["title"])}</a>'
                     f'<div style="font-size:12px;color:#718096">{meta}</div></li>')
            t += [f'- {p["title"]} ({p.get("journal", "")}, {p.get("pub_date", "")})', f'  {p["url"]}']
        h.append("</ul>")
        t.append("")

    h.append(_notice_html(zh) + "</div></body></html>")
    t += _notice_text(zh)
    return subject, "".join(h), "\n".join(t)


def send_email(subject, html_body, text_body, recipients, user, app_password,
               host=None, port=None, smtp_factory=smtplib.SMTP_SSL):
    """Send one message. Recipients are BCC'd (envelope only), so nobody sees anyone else's address."""
    if not recipients:
        raise ValueError("No recipients given.")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr(("Weekly Cat Research", user))
    msg["To"] = formataddr(("Weekly Cat Research", user))
    msg["Date"] = formatdate(localtime=True)
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    with smtp_factory(host or config.SMTP_HOST, port or config.SMTP_PORT,
                      context=ssl.create_default_context()) as s:
        s.login(user, app_password)
        s.send_message(msg, from_addr=user, to_addrs=list(recipients))
    return msg
