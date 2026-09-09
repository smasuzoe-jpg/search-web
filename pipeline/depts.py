# -*- coding: utf-8 -*-
"""
診療科目の抽出。

「呼吸器内科」を「内科」と取り違えないよう、長い科名から順に当て、
一度当たった位置は再利用しない。
"""
import re
from common import nfkc

# 標榜科名。長いものが先に来るよう、使う直前に長さ順へ並べ替える。
DEPARTMENTS = [
    # 内科系
    "総合内科", "呼吸器内科", "循環器内科", "消化器内科", "胃腸内科", "腎臓内科",
    "脳神経内科", "神経内科", "糖尿病内科", "代謝内科", "内分泌内科", "血液内科",
    "感染症内科", "漢方内科", "老年内科", "緩和ケア内科", "人工透析内科",
    "肝臓内科", "膠原病内科", "アレルギー内科", "心療内科", "精神科", "神経科",
    "リウマチ科", "アレルギー科", "小児科", "小児外科", "新生児科", "内科",
    # 外科系
    "消化器外科", "呼吸器外科", "心臓血管外科", "乳腺外科", "内分泌外科",
    "大腸肛門外科", "肛門外科", "脳神経外科", "整形外科", "形成外科",
    "美容外科", "美容皮膚科", "皮膚科", "泌尿器科", "腎泌尿器科", "外科",
    # その他
    "産婦人科", "産科", "婦人科", "眼科", "耳鼻咽喉科", "耳鼻科", "気管食道科",
    "放射線科", "放射線診断科", "放射線治療科", "麻酔科", "ペインクリニック",
    "リハビリテーション科", "病理診断科", "救急科", "総合診療科", "透析",
    "歯科口腔外科", "口腔外科", "矯正歯科", "小児歯科", "審美歯科", "歯科",
    # 標榜科ではないが実務で使う区分
    "人間ドック", "健康診断", "健診", "予防接種", "訪問診療", "在宅診療",
    "禁煙外来", "睡眠外来", "甲状腺", "性感染症", "内視鏡",
]
_SORTED = sorted(set(DEPARTMENTS), key=len, reverse=True)

TAG = re.compile(r"<[^>]+>")
SCRIPT = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
HEADING = re.compile(r"<h[1-3][^>]*>(.*?)</h[1-3]>", re.S | re.I)
NAV = re.compile(r"<(nav|ul)\b.*?</\1>", re.S | re.I)
DEPT_SECTION = re.compile(r"(診療科目|診療科|標榜科|診療内容|診療案内)")


def _text(fragment):
    s = SCRIPT.sub(" ", fragment or "")
    s = TAG.sub(" ", s)
    return nfkc(s)


def find_departments(text):
    """長い科名を優先して拾う。当たった位置は伏せて二重取りを防ぐ。"""
    t = nfkc(text or "")
    found, marked = [], list(t)
    for d in _SORTED:
        start = 0
        while True:
            i = t.find(d, start)
            if i < 0:
                break
            if all(marked[j] is not None for j in range(i, i + len(d))):
                found.append(d)
                for j in range(i, i + len(d)):
                    marked[j] = None
                break                      # 同じ科名は1回数えれば足りる
            start = i + 1
    return found


def extract_departments(html):
    """
    出所ごとに分けて返す。
      title    … <title>と見出し。最も信頼できる
      section  … 「診療科目」等の見出し周辺
      nav      … メニュー
    """
    if not html:
        return {"title": [], "section": [], "nav": []}

    head = " ".join(TITLE.findall(html)[:1] + HEADING.findall(html)[:6])
    title_hits = find_departments(_text(head))

    body = _text(html)
    section_hits = []
    m = DEPT_SECTION.search(body)
    if m:
        section_hits = find_departments(body[m.start(): m.start() + 500])

    nav_hits = []
    for nm in list(NAV.finditer(html))[:4]:
        nav_hits += find_departments(_text(nm.group(0)))

    dedup = lambda xs: list(dict.fromkeys(xs))
    return {"title": dedup(title_hits), "section": dedup(section_hits),
            "nav": dedup(nav_hits)}


def departments_from_name(name):
    """施設名から拾う。サイトが取れない施設でも使える。"""
    return find_departments(name)
