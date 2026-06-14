# 🚌 高速バス最安値トラッカー

バス比較なび（bushikaku.net）のお気に入り区間について、出発日別の最安値を**自動収集**し、**GitHub Pages でグラフ表示**するシステムです。

---

## 目次

- [機能](#機能)
- [システム構成](#システム構成)
- [使用技術](#使用技術)
- [リポジトリ構成](#リポジトリ構成)
- [構築手順](#構築手順)
- [使い方](#使い方)
- [ローカル実行](#ローカル実行)
- [データ仕様](#データ仕様)
- [トラブルシューティング](#トラブルシューティング)
- [注意事項](#注意事項)

---

## 機能

| 機能 | 説明 |
|---|---|
| 自動データ収集 | 月・水・金 JST 10:00 にお気に入り8区間の日付別最安値を取得（今日から60日分） |
| 出発日で探す | 出発日と区間（お気に入り8区間）を指定して、その日の価格推移と現在のお得度を確認 |
| トレンド判定 | 直近7日間の価格変化を「↘ 下落中 / ↗ 上昇中 / → 横ばい」で表示 |
| 統計表示 | 現在値・過去最安値・過去最高値・記録日数を表示 |
| データ蓄積 | 取得データを CSV に追記、GitHub リポジトリで管理 |

---

## システム構成

```
【月・水・金 JST 10:00】scrape-daily ジョブ（週3回・自動）
    ↓
scrape_daily.py 実行（日付別・お気に入り区間）
  └─ routes.json に登録した8区間を対象
  └─ 今日から60日分の日付別最安値を取得（SLEEP 3秒/リクエスト）
  └─ data/daily_prices.csv に本日分を追記
  └─ docs/daily_data.json をグラフ用に再生成
  └─ git commit & push
    ↓
GitHub Pages が自動反映
    ↓
ブラウザで index.html を開くと最新グラフを確認できる
```

---

## 使用技術

| 種別 | 技術・バージョン |
|---|---|
| 言語 | Python 3.13 |
| スクレイピング | requests 2.34.2 / beautifulsoup4 4.15.0 / lxml 6.1.1 |
| CI/CD | GitHub Actions |
| actions/checkout | v6 |
| actions/setup-python | v6 |
| グラフ描画 | Chart.js 4.4.1 |
| ホスティング | GitHub Pages |

---

## リポジトリ構成

```
bus-price-tracker/
├── .github/
│   └── workflows/
│       └── scrape.yml          # 定時実行ワークフロー（月・水・金）
├── scraper/
│   ├── scrape_daily.py         # 日付別スクレイパー（お気に入り区間）
│   ├── routes.json             # お気に入り区間の設定ファイル
│   └── requirements.txt        # Python 依存ライブラリ
├── data/
│   └── daily_prices.csv        # 日付別データ（取得日・出発日・区間・最安値）
├── docs/                       # GitHub Pages のルート
│   ├── index.html              # グラフ表示ページ
│   └── daily_data.json         # グラフ用データ（自動生成・手動編集不要）
├── .gitignore
└── README.md
```

---

## 構築手順

### 前提条件

- GitHub アカウント
- Git がインストールされていること

---

### Step 1. リポジトリを GitHub に作成する

1. GitHub にログインし、右上の **「+」→「New repository」** をクリック
2. 以下の設定でリポジトリを作成する

   | 項目 | 値 |
   |---|---|
   | Repository name | `bus-price-tracker`（任意） |
   | Visibility | **Public**（GitHub Pages の無料利用に必要） |
   | Initialize this repository | チェックしない |

3. 作成後に表示される URL（例: `https://github.com/your-name/bus-price-tracker`）をメモする

---

### Step 2. ファイルをプッシュする

ダウンロードしたファイル一式をローカルに配置し、以下を実行する。

```bash
cd bus-price-tracker

git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/<your-name>/bus-price-tracker.git
git push -u origin main
```

> `<your-name>` は自分の GitHub ユーザー名に置き換えること。

---

### Step 3. GitHub Pages を有効化する

1. GitHub のリポジトリページを開く
2. **「Settings」** タブをクリック
3. 左メニューの **「Pages」** をクリック
4. 「Source」セクションで以下を設定して **「Save」** をクリック

   | 項目 | 値 |
   |---|---|
   | Source | Deploy from a branch |
   | Branch | `main` |
   | Folder | `/docs` |

5. しばらくすると `https://<your-name>.github.io/bus-price-tracker/` でページが公開される

---

### Step 4. Actions の書き込み権限を有効化する

デフォルトでは GitHub Actions からのコミットが禁止されているため、以下で許可する。

1. **「Settings」→「Actions」→「General」** を開く
2. 「Workflow permissions」セクションで **「Read and write permissions」** を選択
3. **「Save」** をクリック

---

### Step 5. 初回データ取得を手動実行する

リポジトリ作成直後はデータが空のため、手動で最初の取得を実行する。

1. **「Actions」** タブをクリック
2. 左メニューの **「Scrape Bus Prices」** をクリック
3. **「Run workflow」→「Run workflow」** をクリック
4. ワークフローが緑のチェックマークで完了することを確認（約 20〜30 分）
5. `data/daily_prices.csv` にデータが追記されていれば成功

以降は**月・水・金 JST 10:00 に自動実行**されます。

---

## 使い方

GitHub Pages の URL（`https://<your-name>.github.io/bus-price-tracker/`）をブラウザで開く。

特定の日程・区間でバスに乗る予定がある場合に、今の価格がお得かどうかを確認できる。

> **対象区間**: `scraper/routes.json` に登録した以下の8区間のみ。
> 東京→京都 / 東京→大阪 / 東京→名古屋 / 東京→仙台 /
> 京都→東京 / 大阪→東京 / 名古屋→東京 / 仙台→東京

**使い方**

1. 左パネルの **「出発日」** に日付を入力する（例: 2026/06/26）
   - 今日から60日先までの日付が対象（それ以降はデータなし）
2. **「出発地」** と **「到着地」** をセレクトボックスで選択する
3. **「グラフを表示」** ボタンをクリックする

**確認できる内容**

| 項目 | 説明 |
|---|---|
| 価格推移グラフ | 記録開始から今日まで、その日のバス価格がどう変化したかを表示 |
| 最安値ポイント | グラフ上で過去最安値の日を緑の点で強調表示 |
| トレンドバッジ | 直近7日間の変化を「↘ 下落中 / ↗ 上昇中 / → 横ばい」で表示 |
| 現在値の色 | 現在値が最安値圏なら緑・最高値圏なら赤で表示 |

**左パネルのクイックサマリー**

出発地・到着地・日付を入力した時点で、以下がすぐ確認できる。

| 項目 | 説明 |
|---|---|
| 現在の最安値 | 直近の記録価格 |
| 過去最安値 | 記録期間中の最低価格 |
| 直近トレンド（7日） | 価格が下がっているか上がっているか |

> **活用例**: 2026年6月26日に東京→京都に行く予定の場合、出発日に「2026-06-26」を入力し区間を選ぶと、その日のバス価格がこれまでどう推移してきたかが一目でわかる。「↘ 下落中」であればもう少し待ってから予約、「↗ 上昇中」であれば早めに予約するという判断ができる。

---

## ローカル実行

スクレイパーをローカルで動かして動作確認する場合の手順。

### 前提条件

- Python 3.13 以上

### 環境準備

```bash
cd bus-price-tracker
pip install -r scraper/requirements.txt
```

### 実行

```bash
python scraper/scrape_daily.py
```

完了すると以下が更新される。

- `data/daily_prices.csv` → 今日から60日分の日付別最安値が追記される
- `docs/daily_data.json` → グラフ用データが再生成される

> リクエスト間隔が 3秒 のため、完了まで約 25 分かかります。

### 実行ログの見方

```
=== DailyPriceScraper start: 2026-06-10 ===
Routes: 8 区間 × 60 日 = 480 リクエスト予定

[東京都→京都府] (tokyo_kyoto)
  2026-06-10: 1,630円
  2026-06-11: 1,630円
  ...
[東京都→大阪府] (tokyo_osaka)
  2026-06-10: 1,500円
  ...
Total: 478 records, failed: 2/480 (0%)
=== Done ===
```

> `[WARN] fetch failed` が出た場合は[トラブルシューティング](#トラブルシューティング)を参照すること。

---

## データ仕様

### data/daily_prices.csv

日付別スクレイパーが毎日追記するデータファイル。`departure_date` が乗車する日付を表す。

```csv
date,departure_date,departure,arrival,price
2026-06-10,2026-06-10,東京都,京都府,1630
2026-06-10,2026-06-11,東京都,京都府,1630
2026-06-10,2026-06-26,東京都,京都府,1800
```

| カラム | 型 | 説明 |
|---|---|---|
| date | YYYY-MM-DD | 取得日（スクレイピング実行日） |
| departure_date | YYYY-MM-DD | 乗車する日付 |
| departure | string | 出発都道府県名 |
| arrival | string | 到着都道府県名 |
| price | int | 直行便最安値（円） |

### docs/daily_data.json

日付別グラフ表示用に自動生成されるファイル。**手動で編集する必要はない。**

区間・乗車日ごとに、取得日と価格の履歴が格納される。

```json
{
  "routes": ["東京都→京都府", "東京都→大阪府"],
  "data": {
    "東京都→京都府": {
      "2026-06-26": [
        {"date": "2026-06-10", "price": 1800},
        {"date": "2026-06-11", "price": 1750}
      ]
    }
  },
  "updated_at": "2026-06-10T00:00:00Z"
}
```

### お気に入り区間の変更

`scraper/routes.json` を編集することで監視する区間を変更できる。

```json
[
  {"slug": "tokyo_kyoto",  "departure": "東京都", "arrival": "京都府"},
  {"slug": "tokyo_osaka",  "departure": "東京都", "arrival": "大阪府"},
  {"slug": "osaka_tokyo",  "departure": "大阪府", "arrival": "東京都"}
]
```

`slug` は `https://www.bushikaku.net/search/{slug}/` の URL に対応する。

---

## トラブルシューティング

### Actions が失敗する

**確認ポイント**

1. `Settings > Actions > General > Workflow permissions` で **Read and write permissions** が有効になっているか確認する
2. Actions タブの失敗したワークフローをクリックし、**「scrape」ジョブ**のログでエラー内容を確認する

**失敗率チェックについて**

スクレイパーは全スラッグのうち 50% 以上の取得に失敗した場合、異常終了（exit code 1）して CSV/JSON を更新しません。
部分的な失敗（50% 未満）は `[WARN]` としてログに記録されつつ、取得できた分のみ保存されます。

**実行スケジュールについて**

| ジョブ | 実行タイミング | 対象 |
|---|---|---|
| scrape-daily | 月・水・金 JST 10:00 | お気に入り8区間の日付別最安値 |

週3回のみ実行のため、火・木・土・日はデータが更新されません。
別の曜日に実行したい場合は `Actions > Scrape Bus Prices > Run workflow` から手動実行できます。

---

### グラフページが表示されない（404）

1. `Settings > Pages` を開く
2. Source が `main` ブランチの `/docs` フォルダに設定されているか確認する
3. 設定後、反映まで最大5分ほどかかる場合がある

---

### データが取得できない（fetch failed: 403）

サイト側でスクレイピング制限がかかっている可能性がある。

`scraper/scrape_daily.py` の `HEADERS` 内の `User-Agent` を変更してみる。

```python
# Chrome (Windows) の例
"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

# Firefox (Windows) の例
"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0"
```

また、リクエスト間隔 `SLEEP_SEC` をさらに長くすることで回避できる場合もある。

```python
SLEEP_SEC = 5.0  # デフォルトは 3.0
```

---

### 同じ日のデータが重複している

スクレイパーは同日のデータを自動で上書きするため通常は重複しないが、万一発生した場合は以下で修正する。

```bash
python3 - << 'EOF'
import csv
from pathlib import Path

path = Path('data/daily_prices.csv')
rows = list(csv.DictReader(path.open(encoding='utf-8')))
seen = set()
deduped = []
for r in reversed(rows):
    key = (r['date'], r['departure_date'], r['departure'], r['arrival'])
    if key not in seen:
        seen.add(key)
        deduped.append(r)
deduped.reverse()
with path.open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['date', 'departure_date', 'departure', 'arrival', 'price'])
    writer.writeheader()
    writer.writerows(deduped)
print(f'Cleaned: {len(deduped)} rows')
EOF
```

> `pandas` は本プロジェクトの依存ライブラリに含まれていないため、標準ライブラリのみで実装しています。

---

### 出発日で探すタブで「データがありません」と表示される

以下のいずれかの理由が考えられる。

- 指定した日付が今日から60日以降（スクレイピング対象外）
- データ収集を開始したばかりでその日付のデータがまだない
- 指定した区間が `routes.json` に登録されていない
- 指定した区間・日付に運行便がない

---

## 注意事項

- 本システムは**個人利用・非商用**の範囲で使用してください
- 取得データはバス比較なびのサイトに依存するため、サイト構造の変更により動作しなくなる場合があります
- スクレイピング間隔は 3秒/リクエスト、実行頻度は週3回（月・水・金）に設定しており、サーバーへの過度な負荷を避けています
- 価格情報はあくまで参考値です。実際の購入は各バス会社・予約サイトで確認してください
