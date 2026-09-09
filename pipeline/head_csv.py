# -*- coding: utf-8 -*-
"""
CSVの先頭N件を、レコード単位で正しく抜き出す。

    python3 pipeline/head_csv.py data/work1.csv 1000 > data/pilot.csv

シェルの head は住所やビル名に改行が含まれる行でレコードを途中で切ってしまう。
"""
import csv, sys
from common import open_csv, log

def main(path, n):
    f = open_csv(path)
    rd = csv.reader(f)
    w = csv.writer(sys.stdout)
    w.writerow(next(rd))
    i = 0
    for row in rd:
        if i >= n:
            break
        w.writerow(row)
        i += 1
    f.close()
    log(f"[head] {i} 件を抜き出しました")

if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
