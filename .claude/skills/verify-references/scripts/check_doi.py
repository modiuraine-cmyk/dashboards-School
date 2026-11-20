#!/usr/bin/env python3
"""يتحقق من DOI عبر Crossref ويطبع البيانات الرسمية للمقارنة.

الاستخدام: python3 check_doi.py DOI [DOI ...]
لكل DOI: الحالة (موجود / غير موجود)، العنوان، المجلة، المؤلفون، سنة النشر الإلكتروني وسنة العدد المطبوع.
APA 7: تُعتمد سنة النسخة النهائية (العدد) إن وُجدت.
"""
import html
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "verify-references-skill/0.1 (academic reference check)"


def year(m, key):
    parts = (m.get(key) or {}).get("date-parts") or [[None]]
    return parts[0][0]


def check(doi):
    doi = doi.strip().removeprefix("https://doi.org/").removeprefix("doi:")
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=20) as r:
                m = json.load(r)["message"]
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return f"❌ {doi}: غير موجود في Crossref (تحقق من DOI أو ابحث بالعنوان)"
            if e.code == 429 and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            return f"⚠️ {doi}: خطأ {e.code} — أعيدي المحاولة أو تحققي عبر doi.org"
        except Exception as e:  # شبكة محجوبة أو انقطاع
            return f"⚠️ {doi}: تعذّر الاتصال ({e}) — تحققي عبر WebSearch/doi.org"
    authors = "; ".join(f"{a.get('family', '')}, {a.get('given', '')}".strip(", ") for a in m.get("author", []))
    online, printed = year(m, "published-online"), year(m, "published-print")
    issue_year = printed or year(m, "issued")
    lines = [
        f"✅ {doi}: موجود",
        f"   العنوان: {html.unescape((m.get('title') or [''])[0])}",
        f"   المجلة: {html.unescape((m.get('container-title') or [''])[0])} | مجلد {m.get('volume', '—')} عدد {m.get('issue', '—')} ص {m.get('page', '—')}",
        f"   المؤلفون: {authors}",
        f"   سنة APA 7: {issue_year}" + (f" (نُشر إلكترونياً {online})" if online and online != issue_year else ""),
        f"   النوع: {m.get('type')}",
    ]
    if issue_year and issue_year < 2020:
        lines.append("   ⏳ قبل 2020")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for d in sys.argv[1:]:
        print(check(d))
