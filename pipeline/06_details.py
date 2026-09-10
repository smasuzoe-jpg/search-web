# -*- coding: utf-8 -*-
"""
STEP6: 採取した診療時間と診療科目を列に整形する。

    python3 pipeline/06_details.py data/list1_verified_details.jsonl > data/list1_details.csv

サイト巡回は済んでいるので、この工程は何度でもやり直せる。
解釈を変えたくなったらここだけ直して再実行すればよい。

出力列:
    医療機関コード, 会社名, ウェブサイトURL,
    診療時間（整形）, 休診日,
    時間帯1開始, 時間帯1終了, 時間帯2開始, 時間帯2終了, 時間帯3開始, 時間帯3終了,
    診療科目, 診療科目1〜5, 診療科目数, 診療科目の出所,
    診療時間の取得元, 診療時間（原文）

時間帯は開始と終了を別のセルに分ける。「18時以降も診療している医院」のような
絞り込みが表計算ソフトでそのままできる。
"""
import csv, json, re, sys
from common import nfkc, log
from depts import departments_from_name

CLOCK = re.compile(r"(\d{1,2})\s*[:：時]\s*(\d{1,2})?")
RANGE = re.compile(r"(\d{1,2}\s*[:：時]\s*\d{0,2})\s*[~〜～\-−–—ー]\s*(\d{1,2}\s*[:：時]\s*\d{0,2})")
CLOSED = re.compile(r"(休診日?|休み|定休日?)\s*[:：]?\s*([^\n。]{1,40})")


def norm_time(s):
    m = CLOCK.search(nfkc(s))
    if not m:
        return ""
    h = int(m.group(1))
    mi = int(m.group(2)) if m.group(2) else 0
    if h > 24 or mi > 59:
        return ""
    return f"{h:02d}:{mi:02d}"


def time_ranges(text):
    """「9:00〜12:30」のような時間帯を、重複を除いて出現順に返す。"""
    out = []
    for a, b in RANGE.findall(nfkc(text)):
        s, e = norm_time(a), norm_time(b)
        if s and e and s != e:
            r = f"{s}-{e}"
            if r not in out:
                out.append(r)
    return out


def closed_days(text):
    t = nfkc(text)
    m = CLOSED.search(t)
    if not m:
        return ""
    tail = m.group(2).strip(" |:：・")
    tail = re.split(r"\s{2,}|\||／", tail)[0].strip()
    return tail[:40]


MAX_SLOTS = 3      # 朝・昼・夜の3診制まで対応する
MAX_DEPTS = 8      # 診療科目を個別セルに展開する上限


def summarize(payload):
    # 表には時間帯が、周辺テキストには休診日が入っていることが多いので両方見る
    raw = "\n".join((payload.get("tables") or []) + (payload.get("context") or [])).strip()
    ranges = time_ranges(raw)[:MAX_SLOTS]
    closed = closed_days(raw)
    parts = []
    if ranges:
        parts.append(" / ".join(ranges))
    if closed:
        parts.append(f"休診: {closed}")

    slots = []
    for i in range(MAX_SLOTS):
        if i < len(ranges):
            st, en = ranges[i].split("-", 1)
        else:
            st = en = ""
        slots += [st, en]

    return {
        "診療時間（整形）": "　".join(parts),
        "休診日": closed,
        "時間帯": slots,          # [開始1, 終了1, 開始2, 終了2, 開始3, 終了3]
        "診療時間（原文）": re.sub(r"\s*\n\s*", " / ", raw)[:900],
    }


def departments(payload):
    """
    出所をまたいで統合する。見出しだけだと標榜科の一部しか載っていないことが多く、
    診療科目欄のほうが網羅的なため、信頼できる順に並べたうえで全部拾う。
    サイトから何も取れないときは施設名から拾う（巡回不要で必ず動く保険）。
    """
    d = payload.get("診療科目") or {}
    merged, sources = [], []
    for key, label in (("title", "見出し"), ("section", "診療科目欄"), ("nav", "メニュー")):
        hits = d.get(key) or []
        if hits:
            sources.append(label)
        for x in hits:
            if x not in merged:
                merged.append(x)
    if merged:
        return merged, "+".join(sources)
    from_name = departments_from_name(payload.get("会社名", ""))
    if from_name:
        return from_name, "施設名"
    return [], ""


def main(path):
    w = csv.writer(sys.stdout)
    slot_cols = []
    for i in range(1, MAX_SLOTS + 1):
        slot_cols += [f"時間帯{i}開始", f"時間帯{i}終了"]
    dept_cols = [f"診療科目{i}" for i in range(1, MAX_DEPTS + 1)]
    w.writerow(["医療機関コード", "会社名", "ウェブサイトURL",
                "診療時間（整形）", "休診日"] + slot_cols +
               ["診療科目"] + dept_cols + ["診療科目数", "診療科目の出所",
                "診療時間の取得元", "診療時間（原文）"])
    n = parsed = with_dept = 0
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        p = json.loads(line)
        n += 1
        s = summarize(p)
        depts, src = departments(p)
        if s["時間帯"][0]:
            parsed += 1
        if depts:
            with_dept += 1
        d5 = (depts + [""] * MAX_DEPTS)[:MAX_DEPTS]
        w.writerow([p.get("医療機関コード", ""), p.get("会社名", ""),
                    p.get("ウェブサイトURL", ""),
                    s["診療時間（整形）"], s["休診日"]] + s["時間帯"] +
                   ["・".join(depts)] + d5 + [len(depts), src,
                    p.get("診療時間の取得元", ""), s["診療時間（原文）"]])
    if n:
        log(f"[details] {n}件 / 診療時間 {parsed}件 ({parsed / n:.1%}) "
            f"/ 診療科目 {with_dept}件 ({with_dept / n:.1%})")
    else:
        log("[details] 0件")


if __name__ == "__main__":
    main(sys.argv[1])
