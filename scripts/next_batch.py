# -*- coding: utf-8 -*-
"""未調査の行を N 件出力する。 usage: python3 scripts/next_batch.py [N]"""
import csv, sys, unicodedata, re
n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
done = set()
try:
    for r in csv.DictReader(open('data/found_urls.tsv', encoding='utf-8'), delimiter='\t'):
        done.add(r['医療機関コード'].strip())
except FileNotFoundError:
    pass
rows = list(csv.DictReader(open('data/work_full.csv', encoding='utf-8')))
todo = [r for r in rows if r['医療機関コード（正）'].strip() not in done]
print(f"# 残り {len(todo)} / {len(rows)}", file=sys.stderr)
for r in todo[:n]:
    print(f"{r['医療機関コード（正）']}\t{r['検索クエリ']}\t{r['市区町村']}")
