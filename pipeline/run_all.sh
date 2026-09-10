#!/usr/bin/env bash
# 1ファイル分をSTEP1からSTEP5まで通す。
#
#   ./pipeline/run_all.sh <入力CSV> <出力プレフィクス> [オープンデータDIR]
#
# 例（3ファイルを並列で回す）:
#   export SERPER_API_KEY=xxxxx
#   ./pipeline/run_all.sh data/list1.csv data/out1 &
#   ./pipeline/run_all.sh data/list2.csv data/out2 &
#   ./pipeline/run_all.sh data/list3.csv data/out3 &
#   wait
#
# 各STEPは中断・再開できる。落ちたら同じコマンドを再実行すれば続きから走る。
set -euo pipefail

IN="${1:?入力CSVを指定してください}"
OUT="${2:?出力プレフィクスを指定してください}"
OPENDATA="${3:-data/opendata}"
HERE="$(cd "$(dirname "$0")" && pwd)"
LOG="${OUT}_run.log"

run() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; "$@" 2>> "$LOG"; }

mkdir -p "$(dirname "$OUT")" "$OPENDATA"
echo "=== $(date) start $IN ===" >> "$LOG"

# STEP1 正規化・重複判定・検索クエリ生成（ネットワーク不要）
[ -f "${OUT}_work.csv" ] || run python3 "$HERE/01_prepare.py" "$IN" > "${OUT}_work.csv"

# STEP2 公的オープンデータで一括充足（検索APIを使わない）
[ -f "${OUT}_work2.csv" ] || run python3 "$HERE/02_opendata.py" "${OUT}_work.csv" "$OPENDATA" > "${OUT}_work2.csv"

# STEP3 残りを検索API（要 SERPER_API_KEY）
run python3 "$HERE/03_search.py" "${OUT}_work2.csv" "${OUT}_cand.jsonl"

# STEP4 候補ページを開いて電話・番地・施設名で照合
run python3 "$HERE/04_verify.py" "${OUT}_cand.jsonl" "${OUT}_verified.tsv"

# STEP5 出力。「高」のみ自動反映
run python3 "$HERE/05_export.py" "${OUT}_work2.csv" "${OUT}_verified.tsv" "$OUT"

# STEP6 診療時間と診療科目の整形（サイト巡回済みなので何度でもやり直せる）
[ -f "${OUT}_verified_details.jsonl" ] && \
  run python3 "$HERE/06_details.py" "${OUT}_verified_details.jsonl" > "${OUT}_details.csv"

echo "=== $(date) done $IN ===" >> "$LOG"
# STEP7 監査用と診療時間・科目を1本にまとめる
[ -f "${OUT}_details.csv" ] && \
  run python3 "$HERE/07_merge.py" "${OUT}_audit.csv" "${OUT}_details.csv" > "${OUT}_all.csv"

echo "全項目: ${OUT}_all.csv"
echo "取込用: ${OUT}_import.csv"
echo "監査用: ${OUT}_audit.csv"
echo "診療時間・科目: ${OUT}_details.csv"
