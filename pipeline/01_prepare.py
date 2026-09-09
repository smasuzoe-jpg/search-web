# -*- coding: utf-8 -*-
"""
STEP1: HubSpotエクスポートを正規化し、重複グループと検索クエリを付与する。

    python3 pipeline/01_prepare.py <入力CSV> > data/work.csv

重複判定の優先順位:
  1) 医療機関コードが揃っていれば、それだけで同一性を判定する（1施設=1コード）
  2) コード欠損時は 郵便番号 + 正規化施設名
  3) それも欠ける場合は 都道府県 + 正規化施設名
施設名や住所だけで名寄せすると、同名別施設と同一ビル内の別科が潰れるので使わない。
"""
import csv, sys
from collections import defaultdict
from common import (norm_name, norm_code, norm_zip, build_query,
                    resolve_columns, open_csv, log)

OUT_COLS = ["レコードID", "会社名", "医療機関コード", "郵便番号", "都道府県",
            "住所", "電話番号", "ウェブサイトURL", "正規化名", "名寄せキー種別",
            "重複グループID", "代表フラグ", "誤採用注意", "検索クエリ"]


def dedup_key(r):
    code = norm_code(r["code"])
    if len(code) >= 9:
        return "CODE", code
    z, n = norm_zip(r["zip"]), norm_name(r["name"])
    if z and n:
        return "ZIP+NAME", f"{z}:{n}"
    return "PREF+NAME", f'{r["pref"]}:{n}'


def main(path):
    f = open_csv(path)
    rd = csv.DictReader(f)
    cols = resolve_columns(rd.fieldnames or [])
    for need in ("record_id", "name", "code", "addr"):
        if not cols[need]:
            raise SystemExit(f"必須列が見つかりません: {need} / 実ヘッダ={rd.fieldnames}")
    if not cols["phone"]:
        log("[warn] 電話番号列がありません。STEP4の照合精度が落ちます。"
            "可能なら電話番号を含めて再エクスポートしてください。")

    rows = []
    for src in rd:
        r = {k: (src.get(v) or "").strip() if v else "" for k, v in cols.items()}
        kind, key = dedup_key(r)
        r["_kind"], r["_key"] = kind, key
        rows.append(r)
    f.close()

    groups = defaultdict(list)
    for r in rows:
        groups[(r["_kind"], r["_key"])].append(r)

    gid = {}
    for i, k in enumerate(sorted(groups), 1):
        if len(groups[k]) > 1:
            gid[k] = f"G{i:06d}"

    # 代表行: 既にURLが入っている行を優先、次にレコードIDが新しい行
    for k, members in groups.items():
        members.sort(key=lambda r: (r["url"] == "", -int(r["record_id"] or 0)))
        for j, r in enumerate(members):
            r["_gid"] = gid.get(k, "")
            r["_rep"] = "1" if j == 0 else ""

    # 同名別施設・同一住所別施設は「重複」ではないが、URL誤採用の温床なので印を付ける
    by_name, by_addr = defaultdict(list), defaultdict(list)
    for r in rows:
        by_name[norm_name(r["name"])].append(r)
        by_addr[norm_zip(r["zip"]) + ":" + norm_name(r["addr"])].append(r)
    name_hit = addr_hit = 0
    for r in rows:
        flags = []
        if len(by_name[norm_name(r["name"])]) > 1:
            flags.append("同名別施設あり"); name_hit += 1
        if r["zip"] and len(by_addr[norm_zip(r["zip"]) + ":" + norm_name(r["addr"])]) > 1:
            flags.append("同一住所に別施設あり"); addr_hit += 1
        r["_warn"] = "／".join(flags)

    w = csv.writer(sys.stdout)
    w.writerow(OUT_COLS)
    for r in rows:
        w.writerow([r["record_id"], r["name"], norm_code(r["code"]), norm_zip(r["zip"]),
                    r["pref"], r["addr"], r["phone"], r["url"], norm_name(r["name"]),
                    r["_kind"], r["_gid"], r["_rep"], r["_warn"],
                    build_query(r["name"], r["addr"])])

    dup_rows = sum(len(v) for v in groups.values() if len(v) > 1)
    log(f"[prepare] {len(rows)}件 / 真の重複（同一コード） {len(gid)}組 {dup_rows}行 / "
        f"URL既入力 {sum(1 for r in rows if r['url'])}件")
    log(f"[prepare] 誤採用注意: 同名別施設 {name_hit}行 / 同一住所に別施設 {addr_hit}行")


if __name__ == "__main__":
    main(sys.argv[1])
