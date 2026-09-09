# -*- coding: utf-8 -*-
"""
STEP2: 公的オープンデータで一括マッチング（検索APIを1回も使わない）。

    python3 pipeline/02_opendata.py data/work.csv data/opendata/ > data/work2.csv

data/opendata/ に置いた都道府県別CSVから「医療機関コード」列と
「ホームページ」系の列を自動検出し、コード完全一致でURLを流し込む。
列名は自治体・年度でぶれるため、キーワード一致で拾う方式にしてある。
"""
import csv, glob, os, re, sys
from common import norm_code, open_csv, is_blocked, log

CODE_HINTS = ["医療機関コード", "機関コード", "kikanCd", "医療機関番号"]
URL_HINTS  = ["ホームページ", "ＵＲＬ", "URL", "url", "ウェブサイト", "アドレス"]


def pick(header, hints):
    for h in hints:
        for c in header:
            if h in c:
                return c
    return None


def load_opendata(dirpath):
    table = {}
    files = sorted(glob.glob(os.path.join(dirpath, "**", "*.csv"), recursive=True))
    if not files:
        log(f"[warn] {dirpath} にCSVがありません。STEP2はスキップされます。")
    for p in files:
        f = open_csv(p)
        rd = csv.DictReader(f)
        hdr = rd.fieldnames or []
        cc, uc = pick(hdr, CODE_HINTS), pick(hdr, URL_HINTS)
        if not cc or not uc:
            log(f"[skip] 列を特定できず: {os.path.basename(p)} (code={cc}, url={uc})")
            f.close()
            continue
        n = 0
        for r in rd:
            code, url = norm_code(r.get(cc)), (r.get(uc) or "").strip()
            if len(code) < 9 or not url.lower().startswith("http"):
                continue
            if is_blocked(url):
                continue
            table.setdefault(code, url)
            n += 1
        f.close()
        log(f"[load] {os.path.basename(p)}: URL付き {n}件")
    return table


def main(work_path, opendata_dir):
    table = load_opendata(opendata_dir)
    f = open_csv(work_path)
    rd = csv.DictReader(f)
    out = csv.DictWriter(sys.stdout, fieldnames=list(rd.fieldnames) + ["取得元"])
    out.writeheader()
    filled = already = 0
    total = 0
    for r in rd:
        total += 1
        r["取得元"] = ""
        if r["ウェブサイトURL"].strip():
            already += 1
            r["取得元"] = "元データ"
        elif r["医療機関コード"] in table:
            r["ウェブサイトURL"] = table[r["医療機関コード"]]
            r["取得元"] = "オープンデータ"
            filled += 1
        out.writerow(r)
    f.close()
    log(f"[opendata] 全{total}件 / 元から埋まっていた {already}件 / "
        f"今回充足 {filled}件 / 残り {total - already - filled}件")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
