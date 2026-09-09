# -*- coding: utf-8 -*-
"""
STEP6: 採取した診療時間と診療科目を列に整形する。

    python3 pipeline/06_details.py data/list1_verified_details.jsonl > data/list1_details.csv

サイト巡回は済んでいるので、この工程は何度でもやり直せる。
解釈を変えたくなったらここだけ直して再実行すればよい。

出力列:
    医療機関コード, 会社名, ウェブサイトURL, 診療時間の取得元,
    診療時間（整形）, 休診日, 時間帯1, 時間帯2, 診療科目, 診療科目の出所,
    診療時間（原文）
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


def summarize(payload):
    # 表には時間帯が、周辺テキストには休診日が入っていることが多いので両方見る
    raw = "\n".join((payload.get("tables") or []) + (payload.get("context") or [])).strip()
    ranges = time_ranges(raw)
    closed = closed_days(raw)
    parts = []
    if ranges:
        parts.append(" / ".join(ranges[:4]))
    if closed:
        parts.append(f"休診: {closed}")
    return {
        "診療時間（整形）": "　".join(parts),
        "休診日": closed,
        "時間帯1": ranges[0] if len(ranges) > 0 else "",
        "時間帯2": ranges[1] if len(ranges) > 1 else "",
        "診療時間（原文）": re.sub(r"\s*\n\s*", " / ", raw)[:900],
    }


def departments(payload):
    """
    出所の信頼度順に採用する。titleと見出しが最も確か。
    サイトから取れないときは施設名から拾う（巡回不要で必ず動く保険）。
    """
    d = payload.get("診療科目") or {}
    for key, label in (("title", "見出し"), ("section", "診療科目欄"), ("nav", "メニュー")):
        if d.get(key):
            return d[key], label
    from_name = departments_from_name(payload.get("会社名", ""))
    if from_name:
        return from_name, "施設名"
    return [], ""


def main(path):
    w = csv.writer(sys.stdout)
    w.writerow(["医療機関コード", "会社名", "ウェブサイトURL", "診療時間の取得元",
                "診療時間（整形）", "休診日", "時間帯1", "時間帯2",
                "診療科目", "診療科目の出所", "診療時間（原文）"])
    n = parsed = with_dept = 0
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        p = json.loads(line)
        n += 1
        s = summarize(p)
        depts, src = departments(p)
        if s["時間帯1"]:
            parsed += 1
        if depts:
            with_dept += 1
        w.writerow([p.get("医療機関コード", ""), p.get("会社名", ""),
                    p.get("ウェブサイトURL", ""), p.get("診療時間の取得元", ""),
                    s["診療時間（整形）"], s["休診日"], s["時間帯1"], s["時間帯2"],
                    "・".join(depts), src, s["診療時間（原文）"]])
    if n:
        log(f"[details] {n}件 / 診療時間 {parsed}件 ({parsed / n:.1%}) "
            f"/ 診療科目 {with_dept}件 ({with_dept / n:.1%})")
    else:
        log("[details] 0件")


if __name__ == "__main__":
    main(sys.argv[1])
