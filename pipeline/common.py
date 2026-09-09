# -*- coding: utf-8 -*-
"""正規化と共通ユーティリティ。"""
import csv, os, re, sys, unicodedata
from config import (COLUMN_ALIASES, BLOCKED_DOMAINS, BLOCKED_SUFFIXES,
                    PUBLIC_ONLY_SUFFIXES, PUBLIC_ONLY_PATTERNS,
                    PUBLIC_NAME_KEYWORDS)

LEGAL = ["医療法人社団", "医療法人財団", "一般社団法人", "公益社団法人", "一般財団法人",
         "公益財団法人", "社会医療法人", "特定医療法人", "独立行政法人", "地方独立行政法人",
         "社会福祉法人", "医療法人", "医療生協", "厚生連", "学校法人", "特定非営利活動法人"]
NOISE = re.compile(r"[\s　・･,，.。'’\"“”\-－―ー‐–—_/／\\()（）［］\[\]{}]")
_BLOCK = tuple(BLOCKED_DOMAINS)


def nfkc(s):
    return unicodedata.normalize("NFKC", s or "")


def norm_name(s):
    """法人格と記号を落とした施設名。名寄せと本文照合の両方で使う。"""
    s = nfkc(s)
    for w in LEGAL:
        s = s.replace(w, "")
    return NOISE.sub("", s).lower()


def norm_code(s):
    return re.sub(r"\D", "", s or "")


def norm_hospital_code(s):
    """医療機関コードを10桁に揃える。表計算ソフトが先頭の0を落とすため、
    北海道(01)〜栃木(09)など都道府県番号が1桁の県のコードが9桁になって届く。
    ゼロ詰めしないとオープンデータとの突合が丸ごと失敗する。"""
    d = re.sub(r"\D", "", s or "")
    return d.zfill(10) if 0 < len(d) <= 10 else d


def norm_zip(s):
    return re.sub(r"\D", "", s or "")[:7]


def norm_phone(s):
    """数字だけに落とす。国番号+81は0に戻す。"""
    d = re.sub(r"\D", "", nfkc(s))
    # 「810467468610」のように国番号81が頭に付いた行がある。81を外し、
    # 残りが0で始まらない場合だけ0を補う（二重の0を作らない）。
    if d.startswith("81") and len(d) >= 11:
        d = d[2:]
        if not d.startswith("0"):
            d = "0" + d
    return d


# 「羽村市」を「羽村」で切らないよう、市→区→町→村の順に当てる。
_CITY_PATTERNS = [r"^(.+?市.+?区)", r"^(.+?市)", r"^(.+?区)", r"^(.+?町)", r"^(.+?村)"]


def city_part(addr):
    """住所から市区町村までを切り出す。検索クエリの地名に使う。"""
    a = nfkc(addr)
    for pat in _CITY_PATTERNS:
        m = re.match(pat, a)
        if m:
            return m.group(1)
    return a[:6]


def addr_numbers(addr):
    """住所の丁目・番地・号を数字列にする。'二丁目6番1号' -> ['2','6','1']"""
    a = nfkc(addr)
    tail = a[len(city_part(addr)):] or a
    # 「三崎町」の三を番地と誤読しないよう、丁目/番/号に続く漢数字だけを変換する
    tail = re.sub(r"[〇零一二三四五六七八九十]+(?=丁目|丁|番地|番|号|条)",
                  lambda m: _kanji_num_to_arabic(m.group(0)), tail)
    return re.findall(r"\d+", tail)[:4]


_K = {"〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
      "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _kanji_num_to_arabic(s):
    """漢数字を算用数字に。十の位まで対応（住所の番地はこれで足りる）。"""
    out, buf = [], []

    def flush():
        if not buf:
            return
        tokens, val, has_ten = buf[:], 0, False
        for t in tokens:
            if t == "十":
                has_ten = True
                val = (val or 1) * 10
            else:
                val = val + t if has_ten else val * 10 + t
                has_ten = False
        out.append(str(val))
        buf.clear()

    for ch in s:
        if ch in _K:
            buf.append(_K[ch])
        elif ch == "十":
            buf.append("十")
        else:
            flush()
            out.append(ch)
    flush()
    return "".join(out)


def build_query(name, addr):
    """検索クエリ。施設名は分院名まで残し、市区町村を足して同名別施設を分離する。"""
    return f"{nfkc(name).strip()} {city_part(addr)} 公式サイト"


def url_host(url):
    host = re.sub(r"^https?://", "", url or "").split("/")[0].lower()
    return host.split(":")[0]


def is_blocked(url):
    host = url_host(url)
    if any(host.endswith(sfx) for sfx in BLOCKED_SUFFIXES):
        return True
    return any(host == b or host.endswith("." + b) for b in _BLOCK)


def is_blocked_for(url, name):
    """施設名まで見た除外判定。自治体ドメインは公的施設のときだけ認める。"""
    if is_blocked(url):
        return True
    host = url_host(url)
    is_public_domain = (any(host.endswith(sfx) for sfx in PUBLIC_ONLY_SUFFIXES)
                        or any(re.search(p, host) for p in PUBLIC_ONLY_PATTERNS))
    if is_public_domain:
        return not any(k in (name or "") for k in PUBLIC_NAME_KEYWORDS)
    return False


def resolve_columns(header):
    """実ヘッダから論理名→実列名の対応を作る。見つからない論理名はNone。"""
    got = {}
    for logical, cands in COLUMN_ALIASES.items():
        got[logical] = next((c for c in cands if c in header), None)
    return got


def open_csv(path):
    """UTF-8(BOM可)とCP932を自動判別して開く。"""
    for enc in ("utf-8-sig", "cp932", "utf-8"):
        try:
            f = open(path, encoding=enc, newline="")
            f.readline()
            f.seek(0)
            return f
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"文字コードを判別できません: {path}")


def log(msg):
    sys.stderr.write(msg + "\n")
