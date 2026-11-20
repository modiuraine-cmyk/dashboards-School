#!/usr/bin/env python3
"""تقسيم صفوف ملف (xlsx/csv) على المشرفات حسب «سجل المدارس».

الاستخدام:
  python3 split_by_supervisor.py MASTER REGISTER OUT_DIR [--extra-cols "أ|ب|ج"] [--sheet NAME]

- MASTER: الملف الجديد (مثل «صفر دخول») بصيغة xlsx أو csv.
- REGISTER: ورقة «سجل المدارس» مصدَّرة (xlsx أو csv) وفيها الأعمدة:
  الرقم الوزاري، اسم المدرسة (نور)، المشرفة، أسماء بديلة للمطابقة (اختياري).
- OUT_DIR: يُنشأ فيه ملف xlsx لكل مشرفة + «غير مطابقة.xlsx» + «تقرير التقسيم.txt».

المطابقة بالترتيب: الرقم الوزاري كما هو ← الرقم بعد حذف حرف M ← اسم المدرسة/الأسماء البديلة بعد التطبيع.
لا يُحذف أي صف: كل صف لا يطابق يذهب إلى «غير مطابقة».
"""
import argparse
import csv
import re
import sys
from collections import OrderedDict
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

ID_HEADERS = ["الرقم الوزاري"]
SCHOOL_HEADERS = ["اسم المدرسة", "اسم المدرسة (نور)", "المدرسة"]
SUP_HEADERS = ["المشرفة", "العضوة"]
ALT_HEADER_PREFIX = "أسماء بديلة"


def clean(s):
    return re.sub(r"\s+", " ", str(s if s is not None else "")).strip()


def norm_name(s):
    s = clean(s)
    s = re.sub(r"[ً-ْـ]", "", s)          # تشكيل وتطويل
    s = re.sub("[أإآ]", "ا", s).replace("ة", "ه").replace("ى", "ي")
    s = re.sub(r"[()\-–_.,]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_id(s):
    s = clean(s).upper()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def read_table(path, sheet=None):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
    else:
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb[sheet] if sheet else wb.worksheets[0]
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
    rows = [r for r in rows if any(clean(c) for c in r)]
    if not rows:
        sys.exit(f"الملف فارغ: {path}")
    header = [clean(h) for h in rows[0]]
    return header, rows[1:]


def find_col(header, candidates, required=True, what=""):
    for c in candidates:
        if c in header:
            return header.index(c)
    for i, h in enumerate(header):
        if any(h.startswith(c) for c in candidates):
            return i
    if required:
        sys.exit(f"لم أجد عمود {what}. الأعمدة الموجودة: {header}")
    return None


def build_index(reg_header, reg_rows):
    i_id = find_col(reg_header, ID_HEADERS, what="الرقم الوزاري في السجل")
    i_sc = find_col(reg_header, SCHOOL_HEADERS, what="اسم المدرسة في السجل")
    i_sup = find_col(reg_header, SUP_HEADERS, what="المشرفة في السجل")
    i_alt = next((i for i, h in enumerate(reg_header) if h.startswith(ALT_HEADER_PREFIX)), None)
    by_id, by_name, conflicts = {}, {}, []
    for r in reg_rows:
        r = list(r) + [None] * (len(reg_header) - len(r))
        sup = clean(r[i_sup])
        if not sup:
            continue
        ids = {norm_id(r[i_id])} - {""}
        ids |= {i[1:] for i in ids if i.startswith("M")}
        for k in ids:
            if k in by_id and by_id[k] != sup:
                conflicts.append(f"الرقم {k}: {by_id[k]} / {sup}")
            by_id.setdefault(k, sup)
        names = [r[i_sc]] + (clean(r[i_alt]).split("|") if i_alt is not None and r[i_alt] else [])
        for n in names:
            n = norm_name(n)
            if n:
                if n in by_name and by_name[n] != sup:
                    conflicts.append(f"الاسم {n}: {by_name[n]} / {sup}")
                by_name.setdefault(n, sup)
    return by_id, by_name, conflicts


def write_book(path, header, rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "البيانات"
    ws.sheet_view.rightToLeft = True
    ws.append(header)
    for c in ws[1]:
        c.font = Font(bold=True)
    ws.freeze_panes = "A2"
    for r in rows:
        ws.append(r)
    wb.save(path)


def safe_filename(name):
    return re.sub(r'[\\/:*?"<>|]', "-", clean(name))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("master")
    ap.add_argument("register")
    ap.add_argument("out_dir")
    ap.add_argument("--extra-cols", default="", help="أعمدة متابعة فارغة تُضاف، مفصولة بـ |")
    ap.add_argument("--sheet", default=None, help="اسم الورقة في الملف الأم (الافتراضي: الأولى)")
    a = ap.parse_args()

    m_header, m_rows = read_table(a.master, a.sheet)
    r_header, r_rows = read_table(a.register)
    by_id, by_name, conflicts = build_index(r_header, r_rows)

    i_id = find_col(m_header, ID_HEADERS, required=False)
    i_sc = find_col(m_header, SCHOOL_HEADERS, required=False)
    if i_id is None and i_sc is None:
        sys.exit(f"الملف الأم لا يحوي «الرقم الوزاري» ولا «اسم المدرسة». الأعمدة: {m_header}")

    extra = [clean(x) for x in a.extra_cols.split("|") if clean(x)]
    out_header = m_header + [x for x in extra if x not in m_header]
    pad = len(out_header) - len(m_header)

    groups, unmatched, how = OrderedDict(), [], {"id": 0, "id_noM": 0, "name": 0}
    for r in m_rows:
        r = list(r) + [None] * (len(m_header) - len(r))
        sup = None
        if i_id is not None:
            k = norm_id(r[i_id])
            if k in by_id:
                sup, how["id"] = by_id[k], how["id"] + 1
            elif k.startswith("M") and k[1:] in by_id:
                sup, how["id_noM"] = by_id[k[1:]], how["id_noM"] + 1
        if sup is None and i_sc is not None:
            n = norm_name(r[i_sc])
            if n in by_name:
                sup, how["name"] = by_name[n], how["name"] + 1
        row = r[: len(m_header)] + [None] * pad
        (groups.setdefault(clean(sup), []) if sup else unmatched).append(row)

    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for sup, rows in groups.items():
        write_book(out / f"{safe_filename(sup)}.xlsx", out_header, rows)
    if unmatched:
        write_book(out / "غير مطابقة.xlsx", out_header, unmatched)

    total = sum(len(v) for v in groups.values()) + len(unmatched)
    lines = [
        f"صفوف الملف الأم: {len(m_rows)}",
        f"صفوف موزعة + غير مطابقة: {total}  ({'متطابق ✔' if total == len(m_rows) else 'غير متطابق ✖'})",
        f"عدد ملفات المشرفات: {len(groups)}",
        f"مطابقة بالرقم: {how['id']} | بالرقم بعد حذف M: {how['id_noM']} | بالاسم: {how['name']} | غير مطابقة: {len(unmatched)}",
        "",
        "التوزيع:",
    ] + [f"  {s}: {len(v)}" for s, v in sorted(groups.items(), key=lambda x: -len(x[1]))]
    if unmatched:
        schools = OrderedDict()
        for r in unmatched:
            key = f"{clean(r[i_id]) if i_id is not None else ''} | {clean(r[i_sc]) if i_sc is not None else ''}"
            schools[key] = schools.get(key, 0) + 1
        lines += ["", "مدارس غير موجودة في السجل (أضيفيها أو أضيفي اسمها البديل):"]
        lines += [f"  {k}: {v} صف" for k, v in schools.items()]
    if conflicts:
        lines += ["", "تعارضات في السجل (أُخذت المشرفة الأولى):"] + [f"  {c}" for c in conflicts]
    report = "\n".join(lines)
    (out / "تقرير التقسيم.txt").write_text(report, encoding="utf-8")
    print(report)
    return 0 if total == len(m_rows) else 1


if __name__ == "__main__":
    sys.exit(main())
