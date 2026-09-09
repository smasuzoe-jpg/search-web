# -*- coding: utf-8 -*-
"""パイプライン共通設定。運用に合わせてここだけ書き換える。"""

# --- 入力CSVの列名ゆれ吸収 -------------------------------------------------
# 実ファイルのヘッダ名に合わせて候補を足す。左から順に最初に見つかった列を使う。
COLUMN_ALIASES = {
    "record_id": ["レコードID", "Record ID", "レコードＩＤ"],
    "name":      ["会社名", "医療機関名", "Company name", "施設名"],
    "code":      ["医療機関コード（正）", "医療機関コード", "保険医療機関コード"],
    "zip":       ["郵便番号", "Postal code", "〒"],
    "pref":      ["都道府県／地域", "都道府県", "State/Region"],
    "addr":      ["市区町村", "住所", "City", "所在地"],
    "url":       ["ウェブサイトURL", "Website URL", "ホームページ", "URL"],
    "phone":     ["電話番号", "Phone Number", "TEL", "電話"],   # 無ければ照合精度が落ちる
}

# --- 検索から除外するドメイン ---------------------------------------------
# ポータル・口コミ・求人・地図・SNS。自院サイトだけを残すための最重要設定。
BLOCKED_DOMAINS = [
    # 医療ポータル・口コミ
    "byoinnavi.jp", "caloo.jp", "doctorsfile.jp", "fdoc.jp", "medimap.jp",
    "doctor-map.info", "659naoso.com", "qlife.jp", "hospita.jp", "mrso.jp",
    "itot.jp", "medley.life", "clinic.medley.life", "byoin.me", "iryou.jp",
    "epark.jp", "scuel.me", "medicalnote.jp", "m-life.jp", "estdoc.jp",
    "tokyo-doctors.com", "saitama-doctors.com", "gmo-clinic-map.com",
    "clinic.mynavi.jp", "health.ne.jp", "itsudokomap.info", "navita.co.jp",
    "t-pec.jp", "10man-doc.co.jp", "fastdoctor.jp", "sokuyaku.jp",
    "kireipass.jp", "mymeii.jp", "narne.jp", "opendata-japan.com",
    # 求人
    "indeed.com", "jp.indeed.com", "guppy.jp", "job-medley.com", "jobmedley.com",
    "co-medical.com", "kango-roo.com", "mynavi-iryofukushi.jp",
    "works.medical.nikkeibp.co.jp", "nurse-senka.jp",
    # 地図・電話帳・SNS・その他
    "townpage.goo.ne.jp", "mapion.co.jp", "map.yahoo.co.jp", "navitime.co.jp",
    "ekiten.jp", "facebook.com", "instagram.com", "x.com", "twitter.com",
    "youtube.com", "line.me", "ja.wikipedia.org", "hotpepper.jp", "e-shops.jp",
    "doctorqube.com", "apokul.jp", "icall-web.net", "machimachi.com",
]

# --- 検索プロバイダ ---------------------------------------------------------
# "serper" | "google_cse" | "brave"
SEARCH_PROVIDER = "serper"
SEARCH_RESULTS_PER_QUERY = 5
SEARCH_QPS = 5.0          # 1秒あたりのリクエスト数上限
SEARCH_MAX_RETRY = 3

# --- 照合（検証）フェーズ ---------------------------------------------------
VERIFY_CONCURRENCY = 8
VERIFY_TIMEOUT = 15
VERIFY_USER_AGENT = "Mozilla/5.0 (compatible; facility-url-bot/1.0)"
# 電話一致=3, 番地一致=2, 施設名一致=2, 市区町村一致=1 の重み付け合計で判定
CONFIDENCE_HIGH = 4       # これ以上なら「高」
CONFIDENCE_MID  = 3       # これ以上なら「中」、未満は「低」
# トップページで足りない時に追加で見に行くサブページのヒント語
SUBPAGE_HINTS = ["access", "アクセス", "clinic", "about", "gaiyo", "概要",
                 "information", "info", "contact", "outline"]
