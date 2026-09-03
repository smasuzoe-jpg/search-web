# -*- coding: utf-8 -*-
"""
検索結果(found_urls.tsv) を元CSVにマージして納品用CSVを作る。

    python3 scripts/merge_results.py data/work.csv data/found_urls.tsv > data/output.csv
"""
import csv, sys

def main(work_path, found_path):
    found = {}
    with open(found_path, encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            found[r["医療機関コード"].strip()] = r

    rows = list(csv.DictReader(open(work_path, encoding="utf-8")))
    out = csv.writer(sys.stdout)
    out.writerow(["レコードID", "会社名", "医療機関コード（正）", "郵便番号",
                  "都道府県／地域", "市区町村", "ウェブサイトURL",
                  "重複グループID", "代表フラグ", "URL確度", "判定根拠", "検索クエリ"])
    stats = {"高": 0, "中": 0, "低": 0, "未検出": 0, "未調査": 0}
    for r in rows:
        code = r["医療機関コード（正）"].strip()
        hit = found.get(code)
        url, conf, note = r["ウェブサイトURL"], "", ""
        if hit:
            note = hit["判定根拠"]
            if hit["ウェブサイトURL"] in ("未検出", "未調査"):
                conf = hit["ウェブサイトURL"]
                stats[conf] += 1
            else:
                url = hit["ウェブサイトURL"]
                conf = hit["確度"]
                stats[conf] = stats.get(conf, 0) + 1
        out.writerow([r["レコードID"], r["会社名"], code, r["郵便番号"],
                      r["都道府県／地域"], r["市区町村"], url,
                      r["重複グループID"], r["代表フラグ"], conf, note, r["検索クエリ"]])
    total = len(rows)
    filled = stats["高"] + stats["中"] + stats["低"]
    sys.stderr.write(
        f"[merge] 対象 {total} 件 / URL記入 {filled} 件 "
        f"(高 {stats['高']} / 中 {stats['中']} / 低 {stats['低']}) "
        f"/ 未検出 {stats['未検出']} / 未調査 {stats['未調査']}\n")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
