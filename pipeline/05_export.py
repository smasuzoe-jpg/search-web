# -*- coding: utf-8 -*-
"""
STEP5: 照合結果を統合し、HubSpot取込用CSVと監査用CSVを書き出す。

    python3 pipeline/05_export.py data/work2.csv data/verified.tsv data/out

  data/out_import.csv  … レコードID + ウェブサイトURL のみ（HubSpotに戻す用）
  data/out_audit.csv   … 全項目 + 確度 + 判定根拠 + 重複グループID（人の確認用）

「高」のみ自動反映し、「中」「低」は監査CSVで人が見てから流す運用を推奨。
"""
import csv, sys
from common import open_csv, log

AUTO_APPLY = {"高"}          # 自動反映する確度


def main(work_path, verified_path, out_prefix):
    ver = {}
    with open(verified_path, encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            ver[r["医療機関コード"].strip()] = r

    f = open_csv(work_path)
    rows = list(csv.DictReader(f))
    f.close()

    imp = csv.writer(open(f"{out_prefix}_import.csv", "w", encoding="utf-8-sig", newline=""))
    imp.writerow(["レコードID", "ウェブサイトURL"])
    aud = csv.writer(open(f"{out_prefix}_audit.csv", "w", encoding="utf-8-sig", newline=""))
    aud.writerow(["レコードID", "会社名", "医療機関コード", "郵便番号", "都道府県",
                  "住所", "電話番号", "ウェブサイトURL", "確度", "取得元",
                  "判定根拠", "重複グループID", "代表フラグ", "誤採用注意", "検索クエリ"])

    stats = {"元データ": 0, "オープンデータ": 0, "高": 0, "中": 0, "低": 0,
             "未検出": 0, "未処理": 0}
    applied = 0
    for r in rows:
        url, conf, why = r["ウェブサイトURL"].strip(), "", ""
        src = r.get("取得元", "")
        if url:
            stats[src if src in stats else "元データ"] += 1
            conf = "高"
        else:
            hit = ver.get(r["医療機関コード"])
            if not hit:
                stats["未処理"] += 1
                conf = "未処理"
            else:
                conf = hit["確度"] if hit["確度"] in ("高", "中", "低") else "未検出"
                why = hit["判定根拠"]
                stats[conf] = stats.get(conf, 0) + 1
                if conf in AUTO_APPLY:
                    url, src = hit["ウェブサイトURL"], "検索+照合"
        if url:
            imp.writerow([r["レコードID"], url])
            applied += 1
        aud.writerow([r["レコードID"], r["会社名"], r["医療機関コード"], r["郵便番号"],
                      r["都道府県"], r["住所"], r.get("電話番号", ""), url, conf, src,
                      why, r["重複グループID"], r["代表フラグ"],
                      r.get("誤採用注意", ""), r["検索クエリ"]])

    total = len(rows)
    log(f"[export] 全{total}件 / URL確定 {applied}件 ({applied / total:.1%})")
    for k, v in stats.items():
        log(f"  {k}: {v}")
    log(f"  取込用: {out_prefix}_import.csv / 監査用: {out_prefix}_audit.csv")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
