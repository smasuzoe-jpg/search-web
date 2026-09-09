# -*- coding: utf-8 -*-
"""
STEP3: URL未充足の行だけ検索APIに投げ、候補URLを集める。

    export SERPER_API_KEY=xxxx
    python3 pipeline/03_search.py data/work2.csv data/candidates.jsonl [--limit N]

中断・再開できる。candidates.jsonl に既にあるコードは再検索しない。
APIキーは環境変数からのみ読む（ファイルに書かない）。
"""
import argparse, concurrent.futures as cf, json, os, sys, threading, time
import requests
from common import open_csv, is_blocked, log
import csv
from config import (SEARCH_PROVIDER, SEARCH_RESULTS_PER_QUERY, SEARCH_QPS,
                    SEARCH_MAX_RETRY, SEARCH_CONCURRENCY)

_last = [0.0]
_lock = threading.Lock()


def throttle():
    """並列で投げても全体で SEARCH_QPS を超えないようにする。"""
    gap = 1.0 / SEARCH_QPS
    with _lock:
        wait = gap - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()


def search_serper(q):
    key = os.environ["SERPER_API_KEY"]
    r = requests.post("https://google.serper.dev/search",
                      headers={"X-API-KEY": key, "Content-Type": "application/json"},
                      json={"q": q, "gl": "jp", "hl": "ja",
                            "num": SEARCH_RESULTS_PER_QUERY}, timeout=20)
    r.raise_for_status()
    return [{"url": o.get("link", ""), "title": o.get("title", ""),
             "snippet": o.get("snippet", "")} for o in r.json().get("organic", [])]


def search_google_cse(q):
    key, cx = os.environ["GOOGLE_API_KEY"], os.environ["GOOGLE_CSE_ID"]
    r = requests.get("https://www.googleapis.com/customsearch/v1",
                     params={"key": key, "cx": cx, "q": q, "hl": "ja", "gl": "jp",
                             "num": SEARCH_RESULTS_PER_QUERY}, timeout=20)
    r.raise_for_status()
    return [{"url": o.get("link", ""), "title": o.get("title", ""),
             "snippet": o.get("snippet", "")} for o in r.json().get("items", [])]


def search_brave(q):
    key = os.environ["BRAVE_API_KEY"]
    r = requests.get("https://api.search.brave.com/res/v1/web/search",
                     headers={"X-Subscription-Token": key, "Accept": "application/json"},
                     params={"q": q, "country": "jp", "search_lang": "jp",
                             "count": SEARCH_RESULTS_PER_QUERY}, timeout=20)
    r.raise_for_status()
    return [{"url": o.get("url", ""), "title": o.get("title", ""),
             "snippet": o.get("description", "")}
            for o in r.json().get("web", {}).get("results", [])]


PROVIDERS = {"serper": search_serper, "google_cse": search_google_cse,
             "brave": search_brave}


def run_query(q):
    fn = PROVIDERS[SEARCH_PROVIDER]
    for attempt in range(SEARCH_MAX_RETRY):
        throttle()
        try:
            return fn(q)
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else 0
            if code in (429, 500, 502, 503) and attempt < SEARCH_MAX_RETRY - 1:
                time.sleep(2 ** attempt * 2)   # 2s, 4s, 8s
                continue
            raise
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work"); ap.add_argument("outfile")
    ap.add_argument("--limit", type=int, default=0, help="1回の実行で処理する上限件数")
    a = ap.parse_args()

    done = set()
    if os.path.exists(a.outfile):
        with open(a.outfile, encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(json.loads(line)["医療機関コード"])
                except Exception:
                    pass
        log(f"[resume] 済み {len(done)}件を読み込み")

    f = open_csv(a.work)
    todo = [r for r in csv.DictReader(f)
            if not (r.get("ウェブサイトURL") or "").strip()
            and (r.get("医療機関コード") or "") not in done]
    f.close()
    if a.limit:
        todo = todo[:a.limit]
    log(f"[search] 対象 {len(todo)}件 provider={SEARCH_PROVIDER}")

    g = lambda r, k: r.get(k) or ""

    stop_flag = threading.Event()

    def one(r):
        """1件検索して保存用の辞書を返す。失敗は例外のまま呼び出し元へ渡す。"""
        if stop_flag.is_set():
            raise RuntimeError("打ち切り済み")   # クレジットを無駄に消費しない
        hits = run_query(g(r, "検索クエリ"))
        cands = [h for h in hits if h["url"] and not is_blocked(h["url"])]
        return {"医療機関コード": g(r, "医療機関コード"), "会社名": g(r, "会社名"),
                "住所": g(r, "住所"), "電話番号": g(r, "電話番号"),
                "検索クエリ": g(r, "検索クエリ"),
                "候補": cands[:SEARCH_RESULTS_PER_QUERY]}

    n = 0
    stop = False
    with open(a.outfile, "a", encoding="utf-8") as out:
        with cf.ThreadPoolExecutor(SEARCH_CONCURRENCY) as ex:
            futs = {ex.submit(one, r): r for r in todo}
            for fut in cf.as_completed(futs):
                r = futs[fut]
                try:
                    rec = fut.result()
                except Exception as e:
                    # キー切れ・クレジット超過は続けても無駄なので打ち切り、再開に任せる
                    if not stop:
                        log(f"[error] {g(r, '医療機関コード')} {g(r, '会社名')}: {e}")
                        log("[search] 以降を打ち切ります。原因を直して再実行すれば続きから走ります。")
                        stop = True
                        stop_flag.set()
                    continue
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n += 1
                # Googleドライブ上では1件ごとのflushが極端に遅いので50件ごとにまとめる。
                # 中断時に失うのは最大50件で、再開すればその分だけ検索し直される。
                if n % 50 == 0:
                    out.flush()
                if n % 500 == 0:
                    log(f"  ... {n}/{len(todo)}")
        out.flush()
    log(f"[search] 完了 {n}件 検索実行 / 累計 {len(done) + n}件")


if __name__ == "__main__":
    main()
