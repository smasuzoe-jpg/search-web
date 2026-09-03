# -*- coding: utf-8 -*-
"""
HubSpot 医療機関リスト: 重複名寄せ + Web検索クエリ生成

使い方:
    python3 scripts/dedup_and_query.py data/source_head.csv > data/work.csv

出力列:
    レコードID, 会社名, 医療機関コード（正）, 郵便番号, 都道府県／地域, 市区町村,
    ウェブサイトURL, 正規化名, 名寄せキー, 重複グループID, 代表フラグ, 検索クエリ
"""
import csv, re, sys, unicodedata
from collections import defaultdict

# ---------------------------------------------------------------- 正規化
LEGAL = [
    "医療法人社団", "医療法人財団", "一般社団法人", "公益社団法人", "一般財団法人",
    "公益財団法人", "社会医療法人", "特定医療法人", "独立行政法人", "地方独立行政法人",
    "社会福祉法人", "医療法人", "医療生協", "厚生連", "学校法人",
]
NOISE = re.compile(r"[\s　・･,，.。'’\"“”\-－―ー‐–—_/／\\()（）［］\[\]{}]")

def norm(s: str) -> str:
    """全角/半角・記号・法人格を落とした比較用キー"""
    s = unicodedata.normalize("NFKC", s or "")
    for w in LEGAL:
        s = s.replace(w, "")
    s = NOISE.sub("", s)
    return s.lower()

def norm_addr(s: str) -> str:
    """住所: 漢数字/全角数字を半角に寄せ、建物名・階数を落として番地まで比較"""
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("丁目", "-").replace("番地", "-").replace("番", "-").replace("号", "-")
    s = re.sub(r"[^\d\w一-龥ぁ-んァ-ヶ\-]", "", s)
    s = re.sub(r"-+", "-", s)
    return s.lower()

def norm_code(s: str) -> str:
    """医療機関コード（正）: 数字のみ抽出。10桁が正、7桁(都道府県コード欠)も許容"""
    return re.sub(r"\D", "", s or "")

def norm_zip(s: str) -> str:
    return re.sub(r"\D", "", s or "")

# ---------------------------------------------------------------- 名寄せ
def dedup_key(row):
    """
    優先順位:
      1) 医療機関コード（正）が10桁揃っていれば、それが唯一の同一性判定キー
         （厚労省の保険医療機関コードは 1施設1コード。移転・改称してもコードは不変）
      2) コード欠損時は 郵便番号 + 正規化施設名
      3) それも欠ける場合は 正規化施設名 + 都道府県
    """
    code = norm_code(row["医療機関コード（正）"])
    if len(code) >= 9:
        return ("CODE", code)
    z = norm_zip(row["郵便番号"])
    n = norm(row["会社名"])
    if z and n:
        return ("ZIP+NAME", z + ":" + n)
    return ("PREF+NAME", (row["都道府県／地域"] or "") + ":" + n)

# ---------------------------------------------------------------- 検索クエリ
CITY_RE = re.compile(r"^(.+?[市区町村])")
# 施設名だけでは弱いケースに足す地名。政令市は「◯◯市◯◯区」まで採る。
def city_part(addr: str) -> str:
    a = unicodedata.normalize("NFKC", addr or "")
    m = re.match(r"^(.+?市.+?区|.+?[市区町村])", a)
    return m.group(1) if m else a[:6]

def build_query(row) -> str:
    """
    条件指定の方針（無駄な検索を減らすため）:
      - 施設名は完全一致で効かせる（分院名まで含める）
      - 施設名だけで一意にならないため、市区町村（政令市は区まで）を必ず添える
      - 「公式」を添えてポータル/口コミサイトを相対的に下げる
      - 除外ドメインは検索側パラメータ(blocked_domains)で指定する
    """
    name = unicodedata.normalize("NFKC", row["会社名"]).strip()
    return f'{name} {city_part(row["市区町村"])} 公式サイト'

# 医療ポータル/口コミ/求人/地図など「公式HPではない」ドメイン
BLOCKED_DOMAINS = [
    "byoinnavi.jp", "caloo.jp", "doctorsfile.jp", "fdoc.jp", "medimap.jp",
    "doctor-map.info", "659naoso.com", "qlife.jp", "hospita.jp", "mrso.jp",
    "itot.jp", "ekiten.jp", "medley.life", "clinic.medley.life", "byoin.me",
    "indeed.com", "jp.indeed.com", "guppy.jp", "job-medley.com", "jobmedley.com",
    "townpage.goo.ne.jp", "mapion.co.jp", "map.yahoo.co.jp", "navitime.co.jp",
    "facebook.com", "instagram.com", "x.com", "twitter.com", "youtube.com",
    "ja.wikipedia.org", "hotpepper.jp", "e-shops.jp", "iryou.jp",
]

def main(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    groups = defaultdict(list)
    for r in rows:
        groups[dedup_key(r)].append(r)

    out = csv.writer(sys.stdout)
    out.writerow(["レコードID", "会社名", "医療機関コード（正）", "郵便番号",
                  "都道府県／地域", "市区町村", "ウェブサイトURL",
                  "正規化名", "名寄せキー種別", "重複グループID", "代表フラグ", "検索クエリ"])
    gid = 0
    dup_report = []
    for key, members in groups.items():
        gid += 1
        # 代表 = 既にURLが入っている行 > レコードIDが最も新しい(大きい)行
        members.sort(key=lambda r: (r["ウェブサイトURL"].strip() == "", -int(r["レコードID"] or 0)))
        if len(members) > 1:
            dup_report.append((key, [m["会社名"] for m in members]))
        for i, r in enumerate(members):
            out.writerow([r["レコードID"], r["会社名"], r["医療機関コード（正）"], r["郵便番号"],
                          r["都道府県／地域"], r["市区町村"], r["ウェブサイトURL"],
                          norm(r["会社名"]), key[0], f"G{gid:06d}",
                          "代表" if i == 0 else "重複", build_query(r)])
    sys.stderr.write(f"[dedup] 入力 {len(rows)} 行 / ユニーク {len(groups)} 施設 / "
                     f"重複グループ {len(dup_report)} 件\n")
    for key, names in dup_report:
        sys.stderr.write(f"  - {key} :: {names}\n")

if __name__ == "__main__":
    main(sys.argv[1])
