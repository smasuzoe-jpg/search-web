# -*- coding: utf-8 -*-
"""パイプライン共通設定。運用に合わせてここだけ書き換える。"""
import os


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
    # --- パイロット1,000件で実際に誤採用されたポータル ---
    "web-clover.net",       # 医療機関検索ポータル
    "yomiuri.co.jp",        # ヨミドクター（新聞記事）
    "melmo-app.com",        # 予約アプリ
    "yoku-mite.care",       # 医師紹介ポータル
    "med-pro.jp",           # 会員向け医療ポータル
    "smile-nurse.jp",       # 看護師求人
    "jmap.jp",              # 地域医療情報システム
    "kaigokensaku.mhlw.go.jp",
    "wam.go.jp",            # WAM NET（福祉医療機構の情報公表システム）
]

# ドメイン末尾での除外。ここに該当したら候補にしない。
BLOCKED_SUFFIXES = [
    ".mhlw.go.jp",   # 医療情報ネット等、厚労省の検索ポータル
    ".med.or.jp",    # 医師会の医療機関ディレクトリ（公式サイトではない）
]

# 自治体ドメインは「公的施設のときだけ」公式サイトとして認める。
# 県立病院や保健所は lg.jp が正規サイトだが、民間クリニックのlg.jpは案内ページ。
# lg.jp を使わない自治体もある（群馬は pref.gunma.jp、札幌は city.sapporo.jp）。
# 末尾だけでなくホスト名の途中に pref./city./town./vill. が現れる形も拾う。
PUBLIC_ONLY_SUFFIXES = [".lg.jp"]
PUBLIC_ONLY_PATTERNS = [r"(^|\.)pref\.", r"(^|\.)city\.", r"(^|\.)town\.",
                        r"(^|\.)vill\."]
PUBLIC_NAME_KEYWORDS = ["保健所", "県立", "市立", "町立", "村立", "都立", "府立",
                        "道立", "国立", "公立", "大学", "医療センター",
                        "保健センター", "保健福祉", "市民病院", "町民病院"]

# --- 検索プロバイダ ---------------------------------------------------------
# "serper" | "google_cse" | "brave"
SEARCH_PROVIDER = os.environ.get("SEARCH_PROVIDER", "serper")
SEARCH_RESULTS_PER_QUERY = 5
# 1秒あたりのリクエスト数上限。環境変数SEARCH_QPSで上書きできる。
SEARCH_QPS = float(os.environ.get("SEARCH_QPS", "5"))
SEARCH_MAX_RETRY = 3

# --- 照合（検証）フェーズ ---------------------------------------------------
# 同時に開くページ数。環境変数VERIFY_CONCURRENCYで上書きできる。
# 8→24 に上げると照合時間はおよそ3分の1になる。
VERIFY_CONCURRENCY = int(os.environ.get("VERIFY_CONCURRENCY", "8"))
VERIFY_TIMEOUT = 15
VERIFY_USER_AGENT = "Mozilla/5.0 (compatible; facility-url-bot/1.0)"
# 電話一致=3, 番地一致=2, 施設名一致=2, 市区町村一致=1 の重み付け合計で判定
CONFIDENCE_HIGH = 4       # これ以上なら「高」
CONFIDENCE_MID  = 3       # これ以上なら「中」、未満は「低」
# トップページで足りない時に追加で見に行くサブページのヒント語
SUBPAGE_HINTS = ["access", "アクセス", "clinic", "about", "gaiyo", "概要",
                 "information", "info", "contact", "outline"]
