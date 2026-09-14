# -*- coding: utf-8 -*-
"""
STEP12: HubSpot取込用CSVを書き出す。

    python3 pipeline/12_hubspot.py data/list1_all.csv > data/list1_hubspot.csv

列名はHubSpot側のプロパティ名に合わせる。
先頭のレコードIDは、HubSpotが既存の会社レコードを見つけるための鍵。
これが無いと新規レコードが作られてしまうので必ず入れる。

すべての項目が空の行は書かない。取り込んでも何も更新されないため。
"""
import csv, sys
from common import open_csv, log

KEY = "レコードID"

# (出力する列名, 元データの列名)
COLUMNS = [
    ("ウェブサイトURL",   "ウェブサイトURL"),
    ("休診日",            "休診日"),
    ("診療時間帯1 開始",  "時間帯1開始"),
    ("診療時間帯1 終了",  "時間帯1終了"),
    ("診療時間帯2 開始",  "時間帯2開始"),
    ("診療時間帯2 終了",  "時間帯2終了"),
    ("診療時間帯3 開始",  "時間帯3開始"),
    ("診療時間帯3 終了",  "時間帯3終了"),
    ("診療科目",          "診療科目"),
    ("基本領域科",        "基本領域"),
]


def main(all_path):
    f = open_csv(all_path)
    rd = csv.DictReader(f)
    have = set(rd.fieldnames or [])

    missing = [src for _, src in COLUMNS if src not in have]
    if missing:
        log(f"[hubspot] 注意: 元データに無い列があります → {'、'.join(missing)}")
    if KEY not in have:
        f.close()
        raise SystemExit(f"[hubspot] {all_path} に「{KEY}」列がありません。"
                         "HubSpotが既存レコードを見つけられないため中止します。")

    w = csv.writer(sys.stdout)
    w.writerow([KEY] + [dst for dst, _ in COLUMNS])

    n = out = 0
    filled = {dst: 0 for dst, _ in COLUMNS}
    for r in rd:
        n += 1
        rid = (r.get(KEY) or "").strip()
        if not rid:
            continue
        vals = [(r.get(src) or "").strip() for _, src in COLUMNS]
        if not any(vals):
            continue                      # 中身が無い行は取り込まない
        for (dst, _), v in zip(COLUMNS, vals):
            if v:
                filled[dst] += 1
        w.writerow([rid] + vals)
        out += 1
    f.close()

    log(f"[hubspot] 元データ {n:,}件 → 取込対象 {out:,}件"
        + (f" ({out / n:.1%})" if n else ""))
    for dst, _ in COLUMNS:
        c = filled[dst]
        log(f"  {dst}: {c:,}件" + (f" ({c / out:.1%})" if out else ""))


if __name__ == "__main__":
    main(sys.argv[1])
