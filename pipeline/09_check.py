# -*- coding: utf-8 -*-
"""
STEP9: 出来上がった結果を機械的に検査する。

    python3 pipeline/09_check.py /content/drive/MyDrive/medical_url

パイロットのときに手で行った検査を自動化したもの。
巨大なCSVを送らなくても、この出力を貼れば品質が判断できる。
"""
import collections, csv, os, re, sys
from common import is_blocked_for, open_csv, url_host, log


def main(workdir):
    names = ["list1", "list2", "list3"]
    total = collections.Counter()
    hosts = collections.Counter()
    blocked, byurl = [], collections.defaultdict(list)
    hours = depts = basics = filled = rows = 0

    for name in names:
        p = os.path.join(workdir, f"{name}_all.csv")
        if not os.path.exists(p):
            print(f"  {name}_all.csv が見つかりません")
            continue
        f = open_csv(p)
        for r in csv.DictReader(f):
            rows += 1
            conf = (r.get("確度") or "").strip()
            total[conf or "（空）"] += 1
            url = (r.get("ウェブサイトURL") or "").strip()
            if conf == "高" and url:
                filled += 1
                hosts[url_host(url)] += 1
                byurl[url].append(r.get("会社名") or "")
                if is_blocked_for(url, r.get("会社名") or ""):
                    blocked.append((r.get("会社名"), url))
            if (r.get("時間帯1開始") or "").strip():
                hours += 1
            if (r.get("診療科目") or "").strip():
                depts += 1
            if (r.get("基本領域") or "").strip():
                basics += 1
        f.close()

    print(f"\n=== 全体 {rows:,} 件 ===")
    for k in ["高", "中", "低", "未検出", "未処理"]:
        if total.get(k):
            print(f"  {k:6s} {total[k]:7,d}  ({total[k]/rows:5.1%})")
    print(f"\n  診療時間あり {hours:7,d}  ({hours/rows:5.1%})")
    print(f"  診療科目あり {depts:7,d}  ({depts/rows:5.1%})")
    print(f"  基本領域あり {basics:7,d}  ({basics/rows:5.1%})")

    print(f"\n=== 除外すべきURLの混入 ===")
    print(f"  {len(blocked)} 件" + ("（問題なし）" if not blocked else ""))
    for name, url in blocked[:10]:
        print(f"    {name} -> {url[:70]}")

    print(f"\n=== 「高」で多く使われているドメイン（新しいポータルの発見用）===")
    for h, n in hosts.most_common(30):
        if n >= 5:
            print(f"  {n:6,d}  {h}")

    dup = {u: v for u, v in byurl.items() if len(v) >= 5}
    print(f"\n=== 同じURLが5施設以上に付いているもの ===")
    print(f"  {len(dup)} 組" + ("（問題なし）" if not dup else ""))
    for u, v in sorted(dup.items(), key=lambda x: -len(x[1]))[:10]:
        print(f"  {len(v):4d}件  {u[:60]}")
        print(f"         例: {' / '.join(v[:3])}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/content/drive/MyDrive/medical_url")
