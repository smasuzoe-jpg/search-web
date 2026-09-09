# 医療機関ホームページURL一括付与 手順書（確定版）

対象97,000件。方針は **「高」判定のみ自動反映**。中・低・未検出は空欄のまま監査CSVに残す。

想定充足率は6〜7割、機械処理は3ファイル並列で1日以内。

---

## 前提

- **この作業は実行者のPCまたはサーバーで行う。** Claude側の実行環境は検索API・
  医療機関サイト・厚労省の配信元がすべて組織の通信ポリシーで遮断されており、
  STEP2以降を動かせない。
- 検索APIキーが必要（Serper推奨。理由はSTEP3参照）。

```bash
pip install -r pipeline/requirements.txt
```

Googleスプレッドシートの リスト①②③ を、それぞれCSVで
`data/list1.csv` `data/list2.csv` `data/list3.csv` として書き出す。
3ファイルは重複なく分割済み（一意のレコードIDで検証済み）。

想定列: レコードID / 会社名 / 医療機関コード（正） / 郵便番号 / 都道府県／地域 / 市区町村 / 電話番号

---

## 一括実行

```bash
export SERPER_API_KEY=xxxxx        # キーは環境変数のみ。ファイルに書かない
./pipeline/run_all.sh data/list1.csv data/out1 &
./pipeline/run_all.sh data/list2.csv data/out2 &
./pipeline/run_all.sh data/list3.csv data/out3 &
wait
```

各STEPは中断・再開できる。落ちたら同じコマンドを再実行すれば続きから走る。
STEPごとに個別に流したい場合は以下を参照。

---

## STEP1  正規化と重複判定

```bash
python3 pipeline/01_prepare.py data/list1.csv > data/out1_work.csv
```

医療機関コード（10桁・1施設1コード・改称や移転でも不変）を主キーにする。
欠損時は電話番号、次に郵便番号＋施設名にフォールバックする。

**先頭ゼロの補正を内部で行う。** 表計算ソフト経由のエクスポートでは、
都道府県番号が1桁の北海道(01)から栃木(09)までのコードが9桁になって届く。
10桁へゼロ詰めしないとSTEP2の突合がその9県で丸ごと失敗する。

施設名や住所での名寄せはしない。4,764件で検証した結果:

| 判定キー | 重複グループ | 実態 |
|---|---|---|
| 医療機関コード | 0組 | 真の重複なし。一意キーとして使える |
| 施設名（正規化） | 64組 186行 | **同名の別施設**。潰すと別法人が消える |
| 郵便番号＋住所 | 15組 32行 | **同一ビル内の別診療科**。潰すと別施設が消える |

後者2つは統合せず `誤採用注意` 列に印を付けて後工程に渡す。

---

## STEP2  公的オープンデータで一括充足（検索ゼロ・費用ゼロ）

厚生労働省「医療情報ネット」は医療機関コード付きの都道府県別データを公開しており、
報告項目にホームページアドレスが含まれる。各地方厚生局の
「保険医療機関の指定状況」も、コードと正式名称のマスタとして併用できる。

1. 都道府県別CSVをダウンロードし `data/opendata/` に置く
2. 実行する

```bash
python3 pipeline/02_opendata.py data/out1_work.csv data/opendata/ > data/out1_work2.csv
```

医療機関コードと電話番号の両方で引く。列名は年度・自治体でぶれるためキーワードで
自動検出する。`[skip] 列を特定できず` が出たら `pipeline/config.py` の
`CODE_HINTS` / `URL_HINTS` / `PHONE_HINTS` に実際の列名の一部を足す。

**この工程の充足率が検索API課金額を決める。** 必ずパイロットで先に測る。

---

## パイロット（本番前に必ず実施）

いきなり97,000件を流さない。先頭1,000件で実測する。

```bash
head -1001 data/out1_work2.csv > data/pilot.csv
python3 pipeline/03_search.py data/pilot.csv data/pilot_cand.jsonl
python3 pipeline/04_verify.py data/pilot_cand.jsonl data/pilot_verified.tsv
python3 pipeline/05_export.py data/pilot.csv data/pilot_verified.tsv data/pilot
```

`data/pilot_audit.csv` を目視し、3点を確認する。

- STEP2の充足率 → 検索API課金額が確定する
- **「高」判定の適合率 → 今回は「高」を無条件で反映するので最重要。95%を下回るなら
  `config.py` の `CONFIDENCE_HIGH` を4から5へ上げる**
- 「高」なのに誤っていた行の傾向 → `BLOCKED_DOMAINS` に足す

---

## STEP3  残りを検索API

```bash
python3 pipeline/03_search.py data/out1_work2.csv data/out1_cand.jsonl
```

クエリは `施設名（分院名まで）+ 市区町村 + 公式サイト`。
ポータル・口コミ・求人・地図・SNSの約60ドメインを除外済み。これが効率の要で、
除外しないと上位がほぼ全部ポータルで埋まり、照合工程の負荷が数倍になる。

### プロバイダ選択（価格は変動するため要確認）

| API | 1,000件あたり目安 | 日次上限 | 97,000件の所要 |
|---|---|---|---|
| Serper | 0.3〜1ドル | 実質なし | 数時間 |
| Brave Search | 数ドル | プラン次第 | 半日〜 |
| Google Custom Search | 5ドル | **10,000件/日** | **10日** |

Google CSEは日次上限があるため97,000件では10日かかる。Serperを推奨。
`config.py` の `SEARCH_PROVIDER` で切り替える。

---

## STEP4  候補ページを開いて機械照合（精度の要）

```bash
python3 pipeline/04_verify.py data/out1_cand.jsonl data/out1_verified.tsv
```

候補ページを実際に取得し、本文から電話番号・番地・施設名・市区町村を突合して採点する。

| 一致項目 | 配点 |
|---|---|
| 電話番号 | 3 |
| 番地 | 2 |
| 施設名 | 2 |
| 市区町村 | 1 |

合計4点以上が「高」、3点が「中」、それ未満が「低」。
トップページで4点に届かない場合はアクセス・概要ページも見に行く。

実データの罠で検証済み:

| ケース | 得点 | 結果 |
|---|---|---|
| 正しい公式サイト | 8 | 高（自動反映） |
| 同名別施設（松戸の田代内科 vs 世田谷の同名院） | 2 | 低（不採用） |
| 同一ビル別科（戸越パークビル2階の呼吸器内科 vs こどもクリニック） | 3 | 中（不採用） |

同一ビル別科が「高」に届かないのが重要。住所と市区町村は一致してしまうため、
**電話番号が入っていることが誤採用を防ぐ決め手**になっている。

robots.txt を尊重し、同一ホストへは1秒以上あける。並列数は `config.py` の
`VERIFY_CONCURRENCY`（既定8）で調整する。16に上げると所要はほぼ半減する。

---

## STEP5  出力

```bash
python3 pipeline/05_export.py data/out1_work2.csv data/out1_verified.tsv data/out1
```

- `data/out1_import.csv` … レコードIDとURLのみ。HubSpotへ戻す用。**「高」のみ**
- `data/out1_audit.csv` … 全項目＋確度＋判定根拠＋誤採用注意。人の確認用

「高」以外が取込用に混ざらないことは実データ4,764件で検証済み。
後から「中」も採用する方針に変えるときは `05_export.py` の
`AUTO_APPLY` に `"中"` を足して再実行すればよい。STEP3・STEP4は再実行不要。

---

## 想定

| 工程 | 所要 | 費用 |
|---|---|---|
| STEP1 正規化 | 数分 | 0 |
| STEP2 オープンデータ | 半日（DLと列合わせ、ほぼ人手） | 0 |
| パイロット | 1〜2時間 | 数ドル |
| STEP3 検索API | 数時間（3並列） | 30〜300ドル |
| STEP4 照合 | 6〜20時間（3並列で1/3） | 0 |
| STEP5 出力 | 数分 | 0 |

3ファイル並列で **機械処理は1日以内**。充足率6〜7割で約58,000〜68,000件にURLが入る。

残る3万件前後は空欄のまま `_audit.csv` に確度と判定根拠付きで残るので、
後から人手を割ける段になったら、そこだけを対象に作業できる。

---

## 付録  検索APIキーの取得手順

### 前提: 97,000件を完全無料で処理することはできない

主要APIの無料枠は以下のとおり（**価格・上限は変動するため申込時に必ず確認**）。

| API | 無料枠 | 97,000件を無料枠だけで処理した場合 |
|---|---|---|
| Google Custom Search | 100件/日 | 約2年8か月 |
| Serper | 登録時2,500件（一回限り） | 不足 |
| Brave Search | 約2,000件/月 | 約4年 |

Microsoftの Bing Search API は提供終了しているため選択肢にならない。
検索サイトを直接スクレイピングする方法は各社の利用規約で禁じられているため使わない。

### 現実的な進め方

1. **STEP2のオープンデータを先に使い切る。ここは完全に無料で上限もない。**
   充足率次第で検索対象が半減する可能性がある。
2. **パイロット1,000件は無料枠で回す。** Serverの登録時2,500件がちょうど収まる。
   ここでオープンデータ充足率と「高」判定の適合率を実測する。
3. 残件数が確定してから課金を判断する。Serperの実勢は10万件で50ドル前後なので、
   **全件やっても数千円規模**に収まる見込み。想定より安いはず。

---

### Serper（推奨）

1. https://serper.dev にGoogleアカウントでサインアップ
2. 登録時点で2,500クレジットが無料付与される
3. ダッシュボードの「API Key」をコピー
4. 実行時に環境変数へ入れる

```bash
export SERPER_API_KEY=xxxxxxxxxxxxxxxx
```

`pipeline/config.py` の `SEARCH_PROVIDER` は既定で `"serper"`。変更不要。

---

### Google Custom Search（無料100件/日）

1. https://console.cloud.google.com でプロジェクトを作成
2. 「APIとサービス」→「ライブラリ」→ **Custom Search API** を有効化
3. 「認証情報」→「認証情報を作成」→「APIキー」→ 発行された文字列が `GOOGLE_API_KEY`
4. https://programmablesearchengine.google.com で検索エンジンを作成し、
   **「ウェブ全体を検索」をON**にする（既定はサイト指定なので必ず切り替える）
5. 発行された「検索エンジンID」が `GOOGLE_CSE_ID`

```bash
export GOOGLE_API_KEY=xxxxxxxxxxxxxxxx
export GOOGLE_CSE_ID=xxxxxxxxxxxxxxxx
```

`config.py` で `SEARCH_PROVIDER = "google_cse"` に変更する。
無料枠のみで使う場合は1日100件が上限なので、次のように区切って回す。

```bash
python3 pipeline/03_search.py data/out1_work2.csv data/out1_cand.jsonl --limit 100
```

課金を有効にすると1,000件5ドル、日次上限は10,000件になる。

---

### Brave Search（無料約2,000件/月）

1. https://brave.com/search/api/ でアカウント作成
2. 無料プランを選択（クレジットカード登録を求められる場合がある）
3. ダッシュボードの「API Keys」から発行

```bash
export BRAVE_API_KEY=xxxxxxxxxxxxxxxx
```

`config.py` で `SEARCH_PROVIDER = "brave"`、`SEARCH_QPS = 1.0` に変更する
（無料プランは毎秒1リクエスト制限のため）。

---

### キーの取り扱い

- **環境変数のみで渡す。** スクリプトは環境変数からしか読まない。
- リポジトリやスプレッドシートにキーを書かない。
- 共有が必要な場合はパスワード管理ツール経由にする。
