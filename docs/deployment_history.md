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

### F. 無料体験トークンの発行とUI表示 (2026-01-27)
ユーザーがサービスを試せるよう、期間限定（2025/1/1〜1/7）で全銘柄を取得できる「無料体験プラン」を実装。
- **トークン発行**: `5c45b5e5a733d7b1d7d4fc1833cc2287`
- **バックエンド制御**: `trial` プランを新規定義し、リクエストされた日付に関わらず `2025-01-01` 〜 `2025-01-07` のデータを強制的に返すよう `app.py` を修正。
- **UI表示**: `index.html` の上部にグラデーション背景の案内ボックスを追加し、お試しトークンを提示。
