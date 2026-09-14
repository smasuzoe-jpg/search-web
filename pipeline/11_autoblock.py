# -*- coding: utf-8 -*-
"""
STEP11: 結果からポータルサイトを自動検出し、除外リストを作る。

    python3 pipeline/11_autoblock.py /content/drive/MyDrive/medical_url

1つのドメインが多数の施設に付いていたら、それは個々の医院の公式サイトではなく
名簿サイトである。実在するグループ院は多くても20院ほどなので、
それを大きく超えるものを機械的に拾う。

出力: <作業フォルダ>/extra_blocked.txt
この先の工程は環境変数 EXTRA_BLOCKED_FILE でこれを読み込む。
"""
import collections, csv, os, sys
from config import PORTAL_MIN_FACILITIES, PORTAL_ALLOWLIST
from common import open_csv, url_host, is_blocked, log

NAMES = ["list1", "list2", "list3"]


def main(workdir):
    hosts = collections.defaultdict(set)      # ドメイン -> 施設名の集合
    prefs = collections.defaultdict(set)      # ドメイン -> 都道府県の集合
    for name in NAMES:
        p = os.path.join(workdir, f"{name}_audit.csv")
        if not os.path.exists(p):
            continue
        f = open_csv(p)
        for r in csv.DictReader(f):
            if (r.get("確度") or "").strip() != "高":
                continue
            url = (r.get("ウェブサイトURL") or "").strip()
            if not url:
                continue
            h = url_host(url)
            hosts[h].add(r.get("会社名") or "")
            prefs[h].add(r.get("都道府県") or "")
        f.close()

    found = []
    for h, names in hosts.items():
        if len(names) < PORTAL_MIN_FACILITIES:
            continue
        if h in PORTAL_ALLOWLIST or is_blocked("https://" + h + "/"):
            continue
        found.append((len(names), len(prefs[h]), h, sorted(names)[:3]))
    found.sort(reverse=True)

    out = os.path.join(workdir, "extra_blocked.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# {PORTAL_MIN_FACILITIES}施設以上に付いていたドメイン\n")
        for n, np_, h, ex in found:
            f.write(f"{h}\n")

    total = sum(n for n, _, _, _ in found)
    log(f"[autoblock] ポータルとみなしたドメイン {len(found)}件 / 影響する行 {total:,}件")
    log(f"  除外リスト: {out}\n")
    for n, np_, h, ex in found[:40]:
        log(f"  {n:5,d}件 {np_:2d}都道府県  {h}")
        log(f"          例: {' / '.join(x[:18] for x in ex)}")
    if len(found) > 40:
        log(f"  ... ほか {len(found)-40}件")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/content/drive/MyDrive/medical_url")
