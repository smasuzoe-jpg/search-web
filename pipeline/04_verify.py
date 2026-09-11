# -*- coding: utf-8 -*-
"""
STEP4: 候補URLを実際に開いて、電話番号・番地・施設名の一致で確度を機械判定する。

    python3 pipeline/04_verify.py data/candidates.jsonl data/verified.tsv

この工程が同名別施設・同一ビル内別科の誤採用を防ぐ。中断・再開できる。
robots.txt を尊重し、同一ホストへの連続アクセスは間隔をあける。
"""
import concurrent.futures as cf, json, os, re, sys, threading, time
import urllib.robotparser as rp
from urllib.parse import urljoin, urlparse
import requests
from common import (norm_name, norm_phone, addr_numbers, city_part, nfkc, log,
                    is_blocked_for)
from config import (VERIFY_CONCURRENCY, VERIFY_TIMEOUT, VERIFY_USER_AGENT,
                    CONFIDENCE_HIGH, CONFIDENCE_MID, SUBPAGE_HINTS)
from hours import extract_hours, has_hours, HOURS_LINK_HINTS
from depts import extract_departments

TAG = re.compile(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", re.S | re.I)
_robots, _rlock = {}, threading.Lock()
_hostlast = {}
_host_locks, _hl_guard = {}, threading.Lock()
_MISSING = object()
ROBOTS_TIMEOUT = 8
HOST_DELAY = 1.0          # 同じサイトへの連続アクセスをあける秒数


def allowed(url):
    """
    robots.txt で禁止されていないか。取得できない場合は許可扱い。

    取得は必ずロックの外で行う。ロックを持ったまま通信すると、
    応答しないサイトが1つあるだけで全スレッドが止まる。
    """
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    with _rlock:
        cached = _robots.get(base, _MISSING)
    if cached is _MISSING:
        parser = None
        try:
            resp = requests.get(base + "/robots.txt", timeout=ROBOTS_TIMEOUT,
                                headers={"User-Agent": VERIFY_USER_AGENT})
            if resp.status_code == 200:
                parser = rp.RobotFileParser()
                parser.parse(resp.text.splitlines())
        except Exception:
            parser = None
        with _rlock:
            _robots.setdefault(base, parser)
        cached = parser
    return True if cached is None else cached.can_fetch(VERIFY_USER_AGENT, url)


def _host_lock(host):
    with _hl_guard:
        lk = _host_locks.get(host)
        if lk is None:
            lk = _host_locks[host] = threading.Lock()
        return lk


def polite(host):
    """
    同じサイトへの連続アクセスだけをあける。

    待ちは「そのサイト用の鍵」の中で行う。共通の鍵の中で待つと、
    待っている間ほかのサイトの処理まで止まり、並列数が意味をなさなくなる。
    """
    lk = _host_lock(host)
    with lk:
        last = _hostlast.get(host, 0.0)
        wait = HOST_DELAY - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        _hostlast[host] = time.time()


def fetch(url):
    if not allowed(url):
        return ""
    polite(urlparse(url).netloc)
    try:
        r = requests.get(url, timeout=VERIFY_TIMEOUT,
                         headers={"User-Agent": VERIFY_USER_AGENT},
                         allow_redirects=True)
        if r.status_code != 200:
            return ""
        r.encoding = r.apparent_encoding or r.encoding
        return r.text
    except Exception:
        return ""


def subpage_urls(html, base, hints=None, limit=2):
    """下層ページのリンクを拾う。既定はアクセス・概要ページ。"""
    hints = hints or SUBPAGE_HINTS
    out = []
    for m in re.finditer(r'href=["\']([^"\']+)["\']', html, re.I):
        href = m.group(1)
        if any(h in href.lower() for h in hints):
            u = urljoin(base, href)
            if urlparse(u).netloc == urlparse(base).netloc and u not in out:
                out.append(u)
        if len(out) >= limit:
            break
    return out


def text_of(html):
    return nfkc(TAG.sub(" ", html))


def score(rec, text):
    """電話3点・番地2点・施設名2点・市区町村1点。根拠も返す。"""
    pts, why = 0, []
    t = text
    tdigits = re.sub(r"\D", "", t)
    tnorm = norm_name(t)

    phone = norm_phone(rec.get("電話番号", ""))
    if phone and len(phone) >= 9 and phone in tdigits:
        pts += 3; why.append("電話一致")

    nums = addr_numbers(rec.get("住所", ""))
    if len(nums) >= 2:
        seq = "".join(nums[:3])
        hit = sum(1 for n in nums[:3] if re.search(rf"(?<!\d){re.escape(n)}(?!\d)", t))
        if hit >= max(2, len(nums[:3]) - 1) or seq in tdigits:
            pts += 2; why.append("番地一致")

    nm = norm_name(rec.get("会社名", ""))
    if len(nm) >= 3 and nm in tnorm:
        pts += 2; why.append("施設名一致")

    city = norm_name(city_part(rec.get("住所", "")))
    if city and city in tnorm:
        pts += 1; why.append("市区町村一致")
    return pts, why


def hours_from(html, url):
    """採用したページから診療時間を採る。無ければ診療案内ページを1枚だけ見に行く。"""
    payload = extract_hours(html)
    if has_hours(payload):
        return payload, url
    for sub in subpage_urls(html, url, hints=HOURS_LINK_HINTS, limit=1):
        h2 = fetch(sub)
        if h2:
            p2 = extract_hours(h2)
            if has_hours(p2):
                return p2, sub
    return payload, ""


def judge(rec):
    """
    候補を上から順に見て、確度が足りたら打ち切る。

    1施設あたりの取得ページ数がそのまま総時間になるので、無駄な取得をしない。
    下層ページまで見るのは最初の候補だけにする（2番目以降は本命でないことが多い）。
    """
    best = None
    for idx, c in enumerate(rec.get("候補", [])):
        url = c["url"]
        if is_blocked_for(url, rec.get("会社名", "")):
            continue                      # ポータル・医師会・自治体案内は公式サイトではない
        html = fetch(url)
        if not html:
            continue
        text = text_of(html)
        pts, why = score(rec, text)
        if pts < CONFIDENCE_HIGH and idx == 0:    # 足りなければアクセスページも見る
            for sub in subpage_urls(html, url):
                h2 = fetch(sub)
                if h2:
                    p2, w2 = score(rec, text + " " + text_of(h2))
                    if p2 > pts:
                        pts, why = p2, w2 + ["下層ページで確認"]
        if best is None or pts > best[0]:
            best = (pts, url, why, html)
        if pts >= CONFIDENCE_HIGH:                # 「高」に届いたら以降の候補は見ない
            break

    if not best or best[0] < 2:
        top = rec["候補"][0]["url"] if rec.get("候補") else ""
        return ["", "未検出", f"候補{len(rec.get('候補', []))}件すべて照合不一致"
                              + (f"（最有力 {top}）" if top else ""), None]
    pts, url, why, html = best
    conf = "高" if pts >= CONFIDENCE_HIGH else ("中" if pts >= CONFIDENCE_MID else "低")
    payload, src = hours_from(html, url)
    payload["診療科目"] = extract_departments(html)
    payload["医療機関コード"] = rec["医療機関コード"]
    payload["会社名"] = rec.get("会社名", "")
    payload["ウェブサイトURL"] = url
    payload["診療時間の取得元"] = src
    return [url, conf, f"{'・'.join(why)}（スコア{pts}）", payload]


def main(cand_path, out_path):
    done = set()
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            next(f, None)
            for line in f:
                done.add(line.split("\t")[0])
        log(f"[resume] 済み {len(done)}件")

    recs = []
    with open(cand_path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["医療機関コード"] not in done:
                recs.append(r)
    log(f"[verify] 対象 {len(recs)}件 並列={VERIFY_CONCURRENCY}")

    # 診療時間も診療科目も、サイトを開いたこの一度きりしか採れない。必ず同時に保存する。
    details_path = re.sub(r"\.tsv$", "", out_path) + "_details.jsonl"

    new = not os.path.exists(out_path)
    got_hours = 0
    with open(out_path, "a", encoding="utf-8") as out, \
         open(details_path, "a", encoding="utf-8") as hout:
        if new:
            out.write("医療機関コード\t会社名\tウェブサイトURL\t確度\t判定根拠\n")
        with cf.ThreadPoolExecutor(VERIFY_CONCURRENCY) as ex:
            futs = {ex.submit(judge, r): r for r in recs}
            for i, fut in enumerate(cf.as_completed(futs), 1):
                r = futs[fut]
                payload = None
                try:
                    url, conf, why, payload = fut.result()
                except Exception as e:
                    url, conf, why = "", "未検出", f"照合エラー: {e}"
                out.write("\t".join([r["医療機関コード"], r["会社名"],
                                     url or "（未検出）", conf, why]) + "\n")
                if payload:
                    hout.write(json.dumps(payload, ensure_ascii=False) + "\n")
                    if has_hours(payload):
                        got_hours += 1
                if i % 50 == 0:
                    out.flush(); hout.flush()   # ドライブ上の書き込みは50件ごとにまとめる
                if i % 500 == 0:
                    log(f"  ... {i}/{len(recs)}  診療時間 {got_hours}件")
            out.flush(); hout.flush()
    log(f"[verify] 完了 / 診療時間を採取 {got_hours}件 -> {details_path}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
