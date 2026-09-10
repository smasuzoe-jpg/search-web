# -*- coding: utf-8 -*-
"""
STEP7: 監査用CSVと診療時間・診療科目CSVを、医療機関コードで1本にまとめる。

    python3 pipeline/07_merge.py data/out1_audit.csv data/out1_details.csv > data/out1_all.csv

医療機関コードが空の行（元データにコードが無い施設）は、
ウェブサイトURLで突き合わせる。
"""
import csv, sys
from common import open_csv, log

DETAIL_SKIP = {"医療機関コード", "会社名", "ウェブサイトURL"}   # 監査用と重複する列


def key_of(row):
    code = (row.get("医療機関コード") or "").strip()
    return ("CODE", code) if code else ("URL", (row.get("ウェブサイトURL") or "").strip())


def main(audit_path, details_path):
    f = open_csv(details_path)
    rd = csv.DictReader(f)
    detail_cols = [c for c in (rd.fieldnames or []) if c not in DETAIL_SKIP]
    details = {}
    for r in rd:
        k = key_of(r)
        if k[1]:
            details[k] = r
    f.close()

    f = open_csv(audit_path)
    rd = csv.DictReader(f)
    w = csv.writer(sys.stdout)
    w.writerow(list(rd.fieldnames or []) + detail_cols)
    n = hit = 0
    for r in rd:
        n += 1
        d = details.get(key_of(r))
        if d:
            hit += 1
        w.writerow([r.get(c) or "" for c in rd.fieldnames] +
                   [(d.get(c) if d else "") or "" for c in detail_cols])
    f.close()
    log(f"[merge] {n}件 / 診療時間・診療科目が付いたもの {hit}件"
        + (f" ({hit / n:.1%})" if n else ""))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
