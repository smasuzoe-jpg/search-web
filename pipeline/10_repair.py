# -*- coding: utf-8 -*-
"""
STEP10: 医療機関コードを一意キーに使っていた頃の中間ファイルを修復する。

    python3 pipeline/10_repair.py /content/drive/MyDrive/medical_url

やること:
  1. 検索結果(cand.jsonl)にレコードIDを補う
  2. 照合結果(verified.tsv)にレコードIDを補う。コードが空で特定できない行は取り除く
  3. 診療時間・科目(details.jsonl)も同様に揃える

そのあと 04_verify を再実行すると、取り除いた行と未処理の行だけが処理される。
検索クレジットは消費しない。
"""
import csv, json, os, sys
from common import open_csv, log

NAMES = ["list1", "list2", "list3"]


def load_work(path):
    """work.csv から、突合用の索引を作る。"""
    by_code, by_name_addr = {}, {}
    f = open_csv(path)
    for r in csv.DictReader(f):
        rid = (r.get("レコードID") or "").strip()
        code = (r.get("医療機関コード") or "").strip()
        na = (r.get("会社名") or "") + "|" + (r.get("住所") or "")
        if code:
            by_code.setdefault(code, []).append(rid)
        by_name_addr.setdefault(na, []).append(rid)
    f.close()
    # 一意に定まるものだけを使う
    return ({k: v[0] for k, v in by_code.items() if len(v) == 1},
            {k: v[0] for k, v in by_name_addr.items() if len(v) == 1})


def resolve(rec, by_code, by_name_addr):
    rid = (rec.get("レコードID") or "").strip()
    if rid:
        return rid
    code = (rec.get("医療機関コード") or "").strip()
    if code and code in by_code:
        return by_code[code]
    na = (rec.get("会社名") or "") + "|" + (rec.get("住所") or "")
    return by_name_addr.get(na, "")


def repair_cand(path, by_code, by_name_addr):
    if not os.path.exists(path):
        return 0, 0
    out, filled, unresolved = [], 0, 0
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if not (rec.get("レコードID") or "").strip():
            rid = resolve(rec, by_code, by_name_addr)
            if rid:
                rec["レコードID"] = rid
                filled += 1
            else:
                unresolved += 1
                continue                    # 特定できない行は捨てて再検索させる
        out.append(json.dumps(rec, ensure_ascii=False) + "\n")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(out)
    return filled, unresolved


def repair_verified(path, by_code):
    """レコードIDを補う。コードが空で特定できない行は取り除き、照合し直させる。"""
    if not os.path.exists(path):
        return 0, 0
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    if not rows:
        return 0, 0
    filled, dropped, keep = 0, 0, []
    for r in rows:
        rid = (r.get("レコードID") or "").strip()
        if not rid:
            code = (r.get("医療機関コード") or "").strip()
            rid = by_code.get(code, "") if code else ""
            if not rid:
                dropped += 1
                continue
            r["レコードID"] = rid
            filled += 1
        keep.append(r)
    cols = ["レコードID", "医療機関コード", "会社名", "ウェブサイトURL", "確度", "判定根拠"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t",
                           extrasaction="ignore")
        w.writeheader()
        for r in keep:
            w.writerow({c: r.get(c, "") for c in cols})
    return filled, dropped


def repair_details(path, by_code, keep_rids):
    """
    レコードIDを補ってから、照合結果に残っている行だけを残す。

    ここでIDを補わずに捨てると、採取済みの診療時間がすべて失われ、
    全サイトを巡回し直すことになる。
    """
    if not os.path.exists(path):
        return 0, 0
    kept, filled, dropped = [], 0, 0
    for line in open(path, encoding="utf-8"):
        try:
            rec = json.loads(line)
        except Exception:
            continue
        rid = (rec.get("レコードID") or "").strip()
        if not rid:
            code = (rec.get("医療機関コード") or "").strip()
            rid = by_code.get(code, "") if code else ""
            if rid:
                rec["レコードID"] = rid
                filled += 1
        if rid and rid in keep_rids:
            kept.append(json.dumps(rec, ensure_ascii=False) + "\n")
        else:
            dropped += 1
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(kept)
    return filled, dropped


def main(workdir):
    for name in NAMES:
        work = os.path.join(workdir, f"{name}_work.csv")
        if not os.path.exists(work):
            log(f"[{name}] work.csv がありません。飛ばします")
            continue
        by_code, by_na = load_work(work)

        c_filled, c_drop = repair_cand(os.path.join(workdir, f"{name}_cand.jsonl"),
                                       by_code, by_na)
        v_filled, v_drop = repair_verified(os.path.join(workdir, f"{name}_verified.tsv"),
                                           by_code)

        ver_path = os.path.join(workdir, f"{name}_verified.tsv")
        keep = set()
        if os.path.exists(ver_path):
            with open(ver_path, encoding="utf-8") as f:
                for r in csv.DictReader(f, delimiter="\t"):
                    keep.add((r.get("レコードID") or "").strip())
        d_filled, d_drop = repair_details(
            os.path.join(workdir, f"{name}_verified_details.jsonl"), by_code, keep)

        log(f"[{name}] 検索結果: ID補完 {c_filled}件 / 特定不能で削除 {c_drop}件")
        log(f"         照合結果: ID補完 {v_filled}件 / 要やり直し {v_drop}件")
        log(f"         診療時間: ID補完 {d_filled}件 / 不整合を削除 {d_drop}件")

    log("\n修復が終わりました。セル4をもう一度押すと、")
    log("取り除いた行と未処理の行だけが処理されます。検索クレジットはほぼ消費しません。")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/content/drive/MyDrive/medical_url")
