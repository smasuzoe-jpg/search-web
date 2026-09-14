# -*- coding: utf-8 -*-
"""
休診日の正規化。

サイトから採った文章には「1月5日(月)から通常通り診療」「その他に臨時休診あり」
のような説明が混ざる。曜日・祝日・年末年始・長期休暇だけを残し、それ以外は捨てる。
"""
import re
import unicodedata
from common import nfkc

WEEK = "月火水木金土日"

# 休診日らしい部分を切り出す
CLOSED = re.compile(r"(休診日?|休み|定休日?)\s*[:：]?\s*([^\n。]{1,60})")

# 日付に付く曜日は休診日ではない。先に取り除く。
DATE_WEEKDAY = re.compile(r"\d+\s*[月/／]\s*\d+\s*日?\s*[（(][" + WEEK + r"][）)]")
PAREN_AFTER_DATE = re.compile(r"(?<=[0-9])\s*日?\s*[（(][" + WEEK + r"][）)]")
DATE_ONLY = re.compile(r"\d+\s*[月/／]\s*\d+\s*日?|\d+\s*日")

# 第2土曜、第2・4土曜、第1,3木曜
NTH_WEEK = re.compile(
    r"第\s*([1-5１-５一二三四五](?:\s*[・,、/／]\s*第?\s*[1-5１-５一二三四五])*)"
    r"\s*週?\s*([" + WEEK + r"])\s*曜?")

WEEKDAY = re.compile(r"([" + WEEK + r"])\s*曜")
# 「日・祝」のように曜の字を伴わない並記
BARE_WEEK = re.compile(r"(?<![0-9第])([" + WEEK + r"])(?=\s*[・,、／/&]|\s*$)")

LONG_HOLIDAY = [
    (re.compile(r"年末年始|年始年末"), "年末年始"),
    (re.compile(r"お盆|盆休|夏季休暇|夏期休暇|夏季休診|夏休み"), "お盆"),
    (re.compile(r"ゴールデンウィーク|ゴールデンウイーク|ＧＷ|GW"), "ゴールデンウィーク"),
    (re.compile(r"祝祭日|祝日|(?<![0-9])祝(?![日祭])"), "祝日"),
]
NO_HOLIDAY = re.compile(r"年中無休|無休")
KANJI_NUM = {"一": "1", "二": "2", "三": "3", "四": "4", "五": "5"}

_WEEK_ORDER = {f"{w}曜": i for i, w in enumerate(WEEK)}
_TAIL_ORDER = {"祝日": 0, "年末年始": 1, "お盆": 2, "ゴールデンウィーク": 3}


def _rank(x):
    if x.startswith("第"):
        # 第2土曜 → 曜日で揃え、そのあと数字順
        w = x[-2:]
        return (0, _WEEK_ORDER.get(w, 99), x)
    if x in _WEEK_ORDER:
        return (1, _WEEK_ORDER[x], "")
    return (2, _TAIL_ORDER.get(x, 99), "")


def extract_closed(text):
    """本文から休診日の記述を切り出す。"""
    m = CLOSED.search(nfkc(text or ""))
    if not m:
        return ""
    tail = m.group(2).strip(" |:：・")
    return re.split(r"\s{2,}|\||／", tail)[0].strip()


def normalize_closed(text):
    """曜日・祝日・年末年始・長期休暇だけに整える。該当がなければ空。"""
    t = nfkc(text or "")
    if not t:
        return ""
    if NO_HOLIDAY.search(t):
        return "なし"

    t = DATE_WEEKDAY.sub(" ", t)
    t = PAREN_AFTER_DATE.sub(" ", t)
    t = DATE_ONLY.sub(" ", t)

    out = []

    def add(x):
        if x not in out:
            out.append(x)

    for m in NTH_WEEK.finditer(t):
        w = m.group(2)
        for g in re.split(r"[・,、/／第\s]+", m.group(1)):
            if g:
                add(f"第{KANJI_NUM.get(g, unicodedata.normalize('NFKC', g))}{w}曜")
    rest = NTH_WEEK.sub(" ", t)

    for m in WEEKDAY.finditer(rest):
        add(m.group(1) + "曜")
    for m in BARE_WEEK.finditer(rest):
        add(m.group(1) + "曜")
    for pat, label in LONG_HOLIDAY:
        if pat.search(t):
            add(label)

    out.sort(key=_rank)
    return "・".join(out)


def closed_days(text):
    """本文から切り出して整えるところまで一度に行う。"""
    return normalize_closed(extract_closed(text))
