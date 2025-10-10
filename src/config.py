# config.py

import os
from sqlalchemy.engine.url import URL
from dotenv import load_dotenv

# プロジェクトルートにある .env ファイルの内容を環境変数として読み込む
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))


# --- 基本設定 ---
TABLE_NAME = "stockdata"
TICKER_CSV_FILE = "data/tickers.csv"


# --- VPS (Docker) 環境用の接続設定 ---
# .envファイルから読み込まれた環境変数を取得
DB_USER = os.getenv("POSTGRES_USER")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")
DB_HOST = os.getenv("DB_HOST") # docker-composeのサービス名(stock-db)
DB_PORT = os.getenv("DB_PORT", "5432") # コンテナ間の通信なので、ポートは5432
DB_NAME = os.getenv("POSTGRES_DB")

# SQLAlchemy用の接続URLを生成
# f-stringを使って文字列を組み立てる
DATABASE_URL = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}@"
    f"{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# 念のため、DATABASE_URLが正しく構築できているか確認（デバッグ用）
# print(f"Generated DATABASE_URL: {DATABASE_URL}")