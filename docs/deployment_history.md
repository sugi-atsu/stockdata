# プロジェクト分析・環境構築・デプロイ実行記録 (2026-01-27)

## 1. プロジェクト概要
日本株の株価データを収集・蓄積し、プランに応じたCSVダウンロードを提供するシステム。

### 主要コンポーネント
- **src/app.py**: FlaskベースのWebアプリケーション。
- **scripts/StockData_loader.py**: yfinanceからデータを取得しDBへ保存するスクリプト。
- **Database**: PostgreSQL (Dockerコンテナで稼働)。

---

## 2. 4段階の環境構成
「手元の環境を汚さず、確実に本番で動かす」ための多段構成。

| 環境名 | 役割 | 接続先・ホスト名 |
| :--- | :--- | :--- |
| **Local (Mac)** | コード編集、Git操作 | 開発ディレクトリ |
| **Local Docker** | 開発時の動作検証 | `localhost:8001` |
| **VPS Local** | サーバー管理、ソース同期 | `162.43.73.33` |
| **VPS Docker** | 本番稼働、データ蓄積 | `stockdata.marketing-hack.net` |

---

## 3. 今回の実施作業

### A. 環境識別機能の追加 (Local-Dev)
自分が今どの環境を触っているか視覚的に判断できるよう、画面上部に「環境バッジ」を追加。
- `src/config.py`: 環境変数 `ENV_NAME` の読み込み処理を追加。
- `src/app.py`: インデックスページに `env_name` を渡すよう修正。
- `src/templates/index.html`: 環境名に応じた色分けバッジ（緑/橙/赤）を表示するUIとロジックを実装。

### B. ローカルDockerの検証
- `.env` に `ENV_NAME=Local-Docker` を設定。
- `docker compose up -d --build` で起動を確認（オレンジバッジの表示）。

### C. VPSへのデプロイ
1. **GitHubへプッシュ**: ローカルの修正を `main` ブランチへ送信。
2. **VPSへSSH同期**: `ssh` 経由で `/root/stockdata` ディレクトリにて `git pull origin main` を実行。
3. **VPS設定変更**: VPS上の `.env` に `ENV_NAME=VPS-Production` を追記。
4. **ファイアウォール開放**: `ufw allow 8001/tcp` を実行し、外部からのアクセスを許可。
5. **コンテナ再起動**: `docker compose up -d` を実行し、最新コードと設定を反映。

---

## 4. 実行コマンド・メモ

### ローカルでのGit操作
```bash
git add .
git commit -m "Add environment identification badge"
git push origin main
```

### VPSへの接続情報 (SSH)
- **Host**: `162.43.73.33`
- **User**: `root`
- **Key**: `~/my-python-project/FX/sinVPS_SSH.pem`

### デバッグ時の確認コマンド (VPS)
```bash
# ログの確認
docker compose logs stock-app
# 接続テスト
curl http://localhost:8001
```

---

## 5. 現在の状態
- **本番環境(VPS)**: 反映完了。テスト用の環境バッジは削除済み。
- **ソースコード**: `app.py`, `config.py`, `index.html` が最新化され、Gitリポジトリと同期済み。

### E. テスト用バッジの削除 (2026-01-27)
検証が完了したため、以下のUIおよびロジックを全環境から削除。
- `src/templates/index.html` からバッジHTMLとJSを削除。
- `src/app.py` および `src/config.py` から環境識別関連の変数を削除。
- 各環境の `.env` から `ENV_NAME` を削除（任意だが推奨）。

### F. 無料体験トークンの改善とユーザー補助機能 (2026-01-27)
ユーザー体験向上のため、無料体験の案内をシンプルにし、入力補助機能を追加。
- **UI刷新**: グラデーションを廃止し、シンプルな囲み枠のデザインに変更。
- **ワンクリックコピー**: トークンをワンクリックでコピーし、自動的に入力欄へセットするボタンを実装。
- **銘柄クイック選択**: トヨタ系、主力・指数、REIT、ETFなどのカテゴリボタンを追加。クリックすると対応する証券コードがテキストエリアに自動追記される。
- **バリデーション同期**: 無料体験プランでも開始日・終了日のバリデーション（2025/1/1〜1/7）が正しく働くよう修正。

### G. お試し用と購入者用ページの分離 (2026-01-27)
利便性とセキュリティ、ブランドイメージ向上のため、ページを用途別に分離。
- **購入者向けページ (`/`)**: 
    - 不要なお試しトークンの案内を削除。
    - 入力欄のクイック選択ボタン（トヨタ等）を削除し、プロフェッショナルな外観に変更。
- **お試し用ページ (`/trial`)**: 
    - 従来の入力補助機能（トークンコピー、銘柄選択ボタン）を維持。
    - タイトルを「無料体験版」に変更し、初心者向けのUIを提供。
- **実装の詳細**: `src/app.py` に `/trial` ルートを追加。テンプレートを `index.html` と `trial.html` に分割。本番環境へデプロイ完了。
    - **本番URL**: `https://stockdata.marketing-hack.net/`
    - **体験用URL**: `https://stockdata.marketing-hack.net/trial` (注: `//trial` でもアクセス可能)
