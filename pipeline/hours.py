# -*- coding: utf-8 -*-
"""
診療時間の抽出。

方針は「生テキストで採っておき、解釈はあとで何度でもやり直す」。
サイト巡回は一度きりなので、この段階では判断せず、
診療時間らしい塊をできるだけ広く回収する。表記の解釈は 06_details.py で行う。
"""
import re
from common import nfkc

# 診療時間の近くに必ず現れる語
HOURS_KEYS = ("診療時間", "受付時間", "外来受付", "診療案内", "診療日", "休診日",
              "診療時間・", "受付", "外来時間", "営業時間", "開院時間")
WEEKDAY = re.compile(r"[月火水木金土日祝]")
CLOCK = re.compile(r"\d{1,2}\s*[:：時]\s*\d{0,2}")
TAG = re.compile(r"<[^>]+>")
SCRIPT = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
TABLE = re.compile(r"<table\b.*?</table>", re.S | re.I)
WS = re.compile(r"[ \t　]+")


def _text(html_fragment):
    """タグを落として整形。表の行構造は改行として残す。"""
    s = SCRIPT.sub(" ", html_fragment)
    s = re.sub(r"</(tr|p|div|li|h\d|br)\s*>", "\n", s, flags=re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</t[dh]\s*>", " | ", s, flags=re.I)
    s = TAG.sub(" ", s)
    s = nfkc(s).replace("&nbsp;", " ")
    s = WS.sub(" ", s)
    return "\n".join(l.strip() for l in s.split("\n") if l.strip())


def _looks_like_hours(text):
    """曜日と時刻の両方が出てくる塊だけを診療時間の候補とみなす。"""
    return bool(WEEKDAY.search(text)) and len(CLOCK.findall(text)) >= 2


def extract_hours(html, max_chars=4000):
    """
    ページから診療時間らしい塊を集めて返す。
      tables  … 曜日と時刻を含む表（最も精度が高い）
      context … 「診療時間」等の語の周辺テキスト（表が画像のときの保険）
    """
    if not html:
        return {"tables": [], "context": []}

    tables = []
    for m in TABLE.finditer(html):
        t = _text(m.group(0))
        if _looks_like_hours(t):
            tables.append(t[:max_chars])
        if len(tables) >= 3:
            break

    body = _text(html)
    context = []
    for key in HOURS_KEYS:
        for m in re.finditer(re.escape(key), body):
            chunk = body[max(0, m.start() - 100): m.start() + 600]
            if _looks_like_hours(chunk):
                context.append(chunk[:max_chars])
                break
        if len(context) >= 3:
            break

    return {"tables": tables, "context": context}


def has_hours(payload):
    return bool(payload.get("tables") or payload.get("context"))


# 診療時間ページへ辿るためのリンク語
HOURS_LINK_HINTS = ["shinryo", "shinryou", "診療", "時間", "jikan", "gairai", "outpatient",
                    "access", "アクセス", "clinic", "about", "guide", "info"]
