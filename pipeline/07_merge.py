# -*- coding: utf-8 -*-
"""
STEP7: 監査用CSVと診療時間・診療科目CSVを、医療機関コードで1本にまとめる。

    python3 pipeline/07_merge.py data/out1_audit.csv data/out1_details.csv > data/out1_all.csv

医療機関コードが空の行（元データにコードが無い施設）は、
ウェブサイトURLで突き合わせる。
"""
import csv, sys
from common import open_csv, rec_key, log

DETAIL_SKIP = {"レコードID", "医療機関コード", "会社名", "ウェブサイトURL"}  # 監査用と重複


def main(audit_path, details_path):
    f = open_csv(details_path)
    rd = csv.DictReader(f)
    detail_cols = [c for c in (rd.fieldnames or []) if c not in DETAIL_SKIP]
    by_rid, by_code = {}, {}
    for r in rd:
        rid = (r.get("レコードID") or "").strip()
        code = (r.get("医療機関コード") or "").strip()
        if rid:
            by_rid[rid] = r
        if code:
            by_code.setdefault(code, r)
    f.close()

    f = open_csv(audit_path)
    rd = csv.DictReader(f)
    w = csv.writer(sys.stdout)
    w.writerow(list(rd.fieldnames or []) + detail_cols)
    n = hit = 0
    for r in rd:
        n += 1
        rid = (r.get("レコードID") or "").strip()
        code = (r.get("医療機関コード") or "").strip()
        d = by_rid.get(rid) if rid else None
        if d is None and code:
            d = by_code.get(code)
        if d:
            hit += 1
        w.writerow([r.get(c) or "" for c in rd.fieldnames] +
                   [(d.get(c) if d else "") or "" for c in detail_cols])
    f.close()
    log(f"[merge] {n}件 / 診療時間・診療科目が付いたもの {hit}件"
        + (f" ({hit / n:.1%})" if n else ""))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
