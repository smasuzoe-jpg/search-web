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

TAG = re.compile(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", re.S | re.I)
_robots, _rlock = {}, threading.Lock()
_hostlast, _hlock = {}, threading.Lock()


def allowed(url):
    """robots.txt で禁止されていないか。取得できない場合は許可扱い。"""
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    with _rlock:
        if base not in _robots:
            r = rp.RobotFileParser()
            r.set_url(base + "/robots.txt")
            try:
                r.read()
            except Exception:
                r = None
            _robots[base] = r
    r = _robots[base]
    return True if r is None else r.can_fetch(VERIFY_USER_AGENT, url)


def polite(host):
    with _hlock:
        last = _hostlast.get(host, 0)
        wait = 1.0 - (time.time() - last)
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


def subpage_urls(html, base):
    """アクセス・概要ページのリンクを最大2件拾う。番地や電話はここにあることが多い。"""
    out = []
    for m in re.finditer(r'href=["\']([^"\']+)["\']', html, re.I):
        href = m.group(1)
        if any(h in href.lower() for h in SUBPAGE_HINTS):
            u = urljoin(base, href)
            if urlparse(u).netloc == urlparse(base).netloc and u not in out:
                out.append(u)
        if len(out) >= 2:
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


def judge(rec):
    best = None
    for c in rec.get("候補", []):
        url = c["url"]
        if is_blocked_for(url, rec.get("会社名", "")):
            continue                      # ポータル・医師会・自治体案内は公式サイトではない
        html = fetch(url)
        if not html:
            continue
        text = text_of(html)
        pts, why = score(rec, text)
        if pts < CONFIDENCE_HIGH:                 # 足りなければアクセスページも見る
            for sub in subpage_urls(html, url):
                h2 = fetch(sub)
                if h2:
                    p2, w2 = score(rec, text + " " + text_of(h2))
                    if p2 > pts:
                        pts, why = p2, w2 + ["下層ページで確認"]
        if best is None or pts > best[0]:
            best = (pts, url, why)
        if pts >= CONFIDENCE_HIGH + 2:            # 満点近ければ以降の候補は見ない
            break

    if not best or best[0] < 2:
        top = rec["候補"][0]["url"] if rec.get("候補") else ""
        return ["", "未検出", f"候補{len(rec.get('候補', []))}件すべて照合不一致"
                              + (f"（最有力 {top}）" if top else "")]
    pts, url, why = best
    conf = "高" if pts >= CONFIDENCE_HIGH else ("中" if pts >= CONFIDENCE_MID else "低")
    return [url, conf, f"{'・'.join(why)}（スコア{pts}）"]


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

    new = not os.path.exists(out_path)
    with open(out_path, "a", encoding="utf-8") as out:
        if new:
            out.write("医療機関コード\t会社名\tウェブサイトURL\t確度\t判定根拠\n")
        with cf.ThreadPoolExecutor(VERIFY_CONCURRENCY) as ex:
            futs = {ex.submit(judge, r): r for r in recs}
            for i, fut in enumerate(cf.as_completed(futs), 1):
                r = futs[fut]
                try:
                    url, conf, why = fut.result()
                except Exception as e:
                    url, conf, why = "", "未検出", f"照合エラー: {e}"
                out.write("\t".join([r["医療機関コード"], r["会社名"],
                                     url or "（未検出）", conf, why]) + "\n")
                out.flush()
                if i % 200 == 0:
                    log(f"  ... {i}/{len(recs)}")
    log("[verify] 完了")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
