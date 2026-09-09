# -*- coding: utf-8 -*-
"""
STEP2: 公的オープンデータで一括マッチング（検索APIを1回も使わない）。

    python3 pipeline/02_opendata.py data/work.csv data/opendata/ > data/work2.csv

data/opendata/ に置いた都道府県別CSVから「医療機関コード」列と
「ホームページ」系の列を自動検出し、コード完全一致でURLを流し込む。
列名は自治体・年度でぶれるため、キーワード一致で拾う方式にしてある。
"""
import csv, glob, os, re, sys
from common import norm_hospital_code, norm_phone, open_csv, is_blocked, log

CODE_HINTS  = ["医療機関コード", "機関コード", "kikanCd", "医療機関番号"]
URL_HINTS   = ["ホームページ", "ＵＲＬ", "URL", "url", "ウェブサイト", "アドレス"]
PHONE_HINTS = ["電話番号", "電話", "TEL", "ＴＥＬ"]


def pick(header, hints):
    for h in hints:
        for c in header:
            if h in c:
                return c
    return None


def load_opendata(dirpath):
    """コードと電話番号の両方で引ける表を作る。元データにコード列が無い場合は
    電話番号が唯一の確実な結合キーになる。"""
    table = {"code": {}, "phone": {}}
    files = sorted(glob.glob(os.path.join(dirpath, "**", "*.csv"), recursive=True))
    if not files:
        log(f"[warn] {dirpath} にCSVがありません。STEP2はスキップされます。")
    for p in files:
        f = open_csv(p)
        rd = csv.DictReader(f)
        hdr = rd.fieldnames or []
        cc, uc, pc = pick(hdr, CODE_HINTS), pick(hdr, URL_HINTS), pick(hdr, PHONE_HINTS)
        if not uc or not (cc or pc):
            log(f"[skip] 列を特定できず: {os.path.basename(p)} "
                f"(code={cc}, phone={pc}, url={uc})")
            f.close()
            continue
        n = 0
        for r in rd:
            url = (r.get(uc) or "").strip()
            if not url.lower().startswith("http") or is_blocked(url):
                continue
            code = norm_hospital_code(r.get(cc)) if cc else ""
            phone = norm_phone(r.get(pc)) if pc else ""
            if len(code) == 10:
                table["code"].setdefault(code, url)
            if len(phone) >= 9:
                table["phone"].setdefault(phone, url)
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
        else:
            url = (table["code"].get(r["医療機関コード"])
                   or table["phone"].get(norm_phone(r.get("電話番号", ""))))
            if url:
                r["ウェブサイトURL"] = url
                r["取得元"] = "オープンデータ"
                filled += 1
        out.writerow(r)
    f.close()
    log(f"[opendata] 全{total}件 / 元から埋まっていた {already}件 / "
        f"今回充足 {filled}件 / 残り {total - already - filled}件")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
