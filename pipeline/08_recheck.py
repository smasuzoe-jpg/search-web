# -*- coding: utf-8 -*-
"""
STEP8: 除外ルールを追加したあと、影響を受けた行だけをやり直せるようにする。

    python3 pipeline/08_recheck.py data/list1_verified.tsv

いまの除外ルールで弾かれるURLを採用している行を、照合結果から取り除く。
そのあと 04_verify を再実行すると、取り除いた行だけが処理される。
全件の再巡回は起きないので数分で終わり、検索クレジットも消費しない。
"""
import csv, json, os, re, sys
from common import is_blocked_for, log


def main(verified_path):
    if not os.path.exists(verified_path):
        raise SystemExit(f"見つかりません: {verified_path}")
    details_path = re.sub(r"\.tsv$", "", verified_path) + "_details.jsonl"

    with open(verified_path, encoding="utf-8") as f:
        rd = csv.DictReader(f, delimiter="\t")
        cols = rd.fieldnames
        rows = list(rd)

    keep, drop = [], set()
    for r in rows:
        url = (r.get("ウェブサイトURL") or "").strip()
        name = r.get("会社名") or ""
        if url and not url.startswith("（") and is_blocked_for(url, name):
            drop.add((r.get("医療機関コード") or "").strip())
        else:
            keep.append(r)

    if not drop:
        log("[recheck] やり直しが必要な行はありません")
        return

    with open(verified_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t")
        w.writeheader()
        w.writerows(keep)

    if os.path.exists(details_path):
        kept = []
        for line in open(details_path, encoding="utf-8"):
            try:
                if json.loads(line).get("医療機関コード") not in drop:
                    kept.append(line)
            except Exception:
                pass
        with open(details_path, "w", encoding="utf-8") as f:
            f.writelines(kept)

    log(f"[recheck] {len(drop)}件を取り除きました（残り {len(keep)}件）")
    log("  04_verify を再実行すると、取り除いた分だけがやり直されます。")


if __name__ == "__main__":
    main(sys.argv[1])
