#!/usr/bin/env python3
"""يحسب أرقام التقرير الأسبوعي من ورقة «ملخص المتابعة» (csv) حتى لا تُحسب الأرقام يدوياً.

الاستخدام: python3 summarize.py SUMMARY.csv [--today YYYY-MM-DD] [--stale-days 7]
يطبع Markdown: تنبيه الحداثة، توزيع الحالات، جدول العضوات، جدول الأخصائيات، ومن تحتاج متابعة.
"""
import argparse
import csv
import re
import sys
from datetime import date, datetime


def clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def days_ar(n):
    n = int(n)
    if n == 1: return "يوم واحد"
    if n == 2: return "يومان"
    if 3 <= n <= 10: return f"{n} أيام"
    return f"{n} يوماً"


def pct(s):
    m = re.search(r"(\d+(?:\.\d+)?)", str(s or ""))
    return float(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("summary")
    ap.add_argument("--today", default=date.today().isoformat())
    ap.add_argument("--stale-days", type=int, default=7)
    a = ap.parse_args()

    with open(a.summary, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.reader(f)]
    header = [clean(h) for h in rows[0]]
    need = ["المشرفة", "عدد المدارس", "رُفع خلال 7 أيام", "أيام منذ آخر رفع", "نسبة إنجاز الاستمارات", "الحالة"]
    miss = [n for n in need if n not in header]
    if miss:
        sys.exit(f"أعمدة ناقصة: {miss}")
    ix = {n: header.index(n) for n in header}

    members, specialists, updated = [], [], None
    for r in rows[1:]:
        if not r or not clean(r[0]):
            continue
        m = re.search(r"آخر تحديث للتقرير:\s*([\d-]+)", r[0])
        if m:
            updated = m.group(1)
            continue
        if len(r) < len(need) or not clean(r[ix["الحالة"]]):
            continue
        d = {n: clean(r[i]) if i < len(r) else "" for n, i in ix.items()}
        (specialists if d["المشرفة"].startswith("أعمال اخصائية") else members).append(d)

    out = []
    if updated:
        age = (datetime.fromisoformat(a.today).date() - datetime.fromisoformat(updated).date()).days
        flag = "⚠️ البيانات قديمة — حدّثي الملخص قبل الاعتماد على التقرير" if age > a.stale_days else "✔ حديثة"
        out.append(f"**حداثة البيانات:** آخر تحديث {updated} (منذ {days_ar(age)}) — {flag}\n")
    else:
        out.append("**حداثة البيانات:** ⚠️ لم أجد سطر «آخر تحديث للتقرير»\n")

    statuses = {}
    for d in members:
        statuses[d["الحالة"]] = statuses.get(d["الحالة"], 0) + 1
    out.append(f"**العضوات: {len(members)}** — " + "، ".join(f"{k}: {v}" for k, v in sorted(statuses.items(), key=lambda x: -x[1])))
    vals = [pct(d["نسبة إنجاز الاستمارات"]) for d in members if pct(d["نسبة إنجاز الاستمارات"]) is not None]
    if vals:
        out.append(f"متوسط نسبة إنجاز الاستمارات (العضوات): {sum(vals)/len(vals):.0f}% | الوسيط: {sorted(vals)[len(vals)//2]:.0f}%\n")

    def table(items):
        t = ["| المشرفة | المدارس | رُفع خلال 7 أيام | أيام منذ آخر رفع | إنجاز الاستمارات | الحالة |", "|---|---|---|---|---|---|"]
        for d in sorted(items, key=lambda d: (pct(d["نسبة إنجاز الاستمارات"]) or 0), reverse=True):
            t.append(f"| {d['المشرفة']} | {d['عدد المدارس']} | {d['رُفع خلال 7 أيام']} | {d['أيام منذ آخر رفع'] or '—'} | {d['نسبة إنجاز الاستمارات']} | {d['الحالة']} |")
        return t

    out.append("### العضوات (مرتبة حسب نسبة الإنجاز)")
    out += table(members)
    if specialists:
        out.append("\n### الأخصائيات (تُعرض منفصلة لأن نطاقها جميع المدارس)")
        out += table(specialists)

    follow = [d for d in members if d["الحالة"] in ("متأخرة", "لم ترفع أي ملف")]
    if follow:
        out.append("\n### تحتاج متابعة")
        for d in sorted(follow, key=lambda d: -(int(d["أيام منذ آخر رفع"]) if d["أيام منذ آخر رفع"].isdigit() else 999)):
            days = d["أيام منذ آخر رفع"] or "لا يوجد رفع"
            out.append(f"- {d['المشرفة']}: {d['الحالة']} ({days_ar(days)} منذ آخر رفع، إنجاز {d['نسبة إنجاز الاستمارات']})" if d["أيام منذ آخر رفع"] else f"- {d['المشرفة']}: {d['الحالة']} (إنجاز {d['نسبة إنجاز الاستمارات']})")
    print("\n".join(out))


if __name__ == "__main__":
    main()
