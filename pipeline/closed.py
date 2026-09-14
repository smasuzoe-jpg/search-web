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

# 「曜」を伴わない表記。「土、日」「土日祝」「水・木」のいずれも拾う。
# 「平日」「本日」「休診日」の日を曜日と読み違えないよう、前後の字で除く。
BAD_BEFORE = "平本当毎祝連臨翌前先昨今半終全午診休祭第0-9"
BAD_AFTER = "帰程中間数付曜"
BARE_WEEK = re.compile(r"(?<![" + BAD_BEFORE + r"])([" + WEEK + r"]{1,7})"
                       r"(?![" + BAD_AFTER + r"])")

LONG_HOLIDAY = [
    (re.compile(r"年末年始|年始年末"), "年末年始"),
    (re.compile(r"お盆|盆休|夏季休暇|夏期休暇|夏季休診|夏休み"), "お盆"),
    (re.compile(r"ゴールデンウィーク|ゴールデンウイーク|ＧＷ|GW"), "ゴールデンウィーク"),
    (re.compile(r"祝祭日|祝日|(?<![0-9])祝(?![日祭])"), "祝日"),
]
NO_HOLIDAY = re.compile(r"年中無休|無休")
# 休診日の記述が無いページでも「年中無休」とだけ書いてあることがある。
# 「無休」単体は「年末年始以外は無休」のような書き方もあるので採らない。
ALWAYS_OPEN = re.compile(r"年中無休|年中休みなし|土日祝も診療")

# 臨時のお知らせを示す語。これを含む部分は定例の休診日ではないので取り除く。
NOTICE = re.compile(r"通常通り|通常どおり|臨時|変更|お知らせ|振替|代診|予定|"
                    r"から診療|まで休|都合により|当面|終日休診|休診とさせ|"
                    r"詳しくは|ご確認|場合があ")
PAREN = re.compile(r"[（(][^）)]{0,40}[）)]")
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

    # 注記の括弧を外す。お知らせか日付が入っていれば丸ごと捨てる。
    t = PAREN.sub(lambda m: "" if (NOTICE.search(m.group(0))
                                   or re.search(r"\d", m.group(0))) else m.group(0), t)

    # 節に分け、臨時のお知らせの節だけを捨てる。
    # 「日曜、その他に臨時休診あり」なら日曜は残す。
    clauses = [c for c in re.split(r"[、,。\n]", t) if c and not NOTICE.search(c)]
    t = "、".join(clauses)
    if not t:
        return ""

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
    rest = WEEKDAY.sub(" ", rest)          # 拾い終えた「X曜」を消してから並記を探す
    for m in BARE_WEEK.finditer(rest):
        for ch in m.group(1):              # 「土日祝」のように続く表記に対応
            add(ch + "曜")
    for pat, label in LONG_HOLIDAY:
        if pat.search(t):
            add(label)

    out.sort(key=_rank)
    return "・".join(out)


def closed_days(text):
    """本文から切り出して整えるところまで一度に行う。"""
    v = normalize_closed(extract_closed(text))
    if v:
        return v
    # 「休診日」という言葉を使わず「年中無休」とだけ書くサイトを拾う
    if ALWAYS_OPEN.search(nfkc(text or "")):
        return "なし"
    return ""
