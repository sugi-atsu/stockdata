# scripts/create_table.py

import os
import sys
from sqlalchemy import create_engine, text, inspect, Table, Column, String, MetaData, Date, Float, BigInteger, Boolean, DateTime
from sqlalchemy.sql import func

# このスクリプトの親ディレクトリ(/app)を検索パスに追加
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# configモジュールをインポート
import config

def create_tables(engine):
    """
    アプリケーションに必要な全てのテーブルを作成します。
    - stockdata: 日次更新データ
    - stockdata_fixed: 期間固定の買い切りデータ
    - tokens: 認証トークン
    """
    try:
        # メタデータを定義
        metadata = MetaData()

        # --- 1. stockdata テーブル (日次更新用) ---
        Table(
            config.TABLE_NAME, metadata, # "stockdata"
            Column("証券コード", String(10), primary_key=True),
            Column("銘柄名", String(255)),
            Column("日付", Date, primary_key=True),
            Column("始値", Float),
            Column("高値", Float),
            Column("安値", Float),
            Column("終値", Float),
            Column("始値（調整後）", Float),
            Column("高値（調整後）", Float),
            Column("安値（調整後）", Float),
            Column("終値（調整後）", Float),
            Column("出来高", BigInteger)
        )

        # --- 2. stockdata_fixed テーブル (期間固定用) ---
        Table(
            config.TABLE_NAME_FIXED, metadata, # "stockdata_fixed"
            Column("証券コード", String(10), primary_key=True),
            Column("銘柄名", String(255)),
            Column("日付", Date, primary_key=True),
            Column("始値", Float),
            Column("高値", Float),
            Column("安値", Float),
            Column("終値", Float),
            Column("始値（調整後）", Float),
            Column("高値（調整後）", Float),
            Column("安値（調整後）", Float),
            Column("終値（調整後）", Float),
            Column("出来高", BigInteger)
        )

        # --- 3. tokens テーブル (認証用) ---
        Table(
            'tokens', metadata,
            Column('id', BigInteger, primary_key=True, autoincrement=True),
            Column('token', String(255), unique=True, nullable=False, index=True),
            Column('plan_type', String(50), nullable=False), # 'bulk' or 'subscription'
            Column('is_active', Boolean, default=True, nullable=False),
            Column('created_at', DateTime, server_default=func.now())
        )

        # データベースにテーブルを作成する（存在しない場合のみ）
        print("Executing CREATE ALL TABLES statement...")
        metadata.create_all(engine, checkfirst=True)
        
        # テーブルが存在するかを再確認
        inspector = inspect(engine)
        required_tables = [config.TABLE_NAME, config.TABLE_NAME_FIXED, 'tokens']
        existing_tables = inspector.get_table_names()
        
        all_ok = True
        for table in required_tables:
            if table in existing_tables:
                print(f"Table '{table}' created successfully or already exists.")
            else:
                print(f"FAILED to create table '{table}'.")
                all_ok = False
        
        if all_ok:
            print("All tables are ready.")

    except Exception as e:
        print(f"An error occurred during table creation: {e}")

def main():
    """
    メインの実行関数
    """
    # configから変数を読み込む
    DATABASE_URL = config.DATABASE_URL
    
    try:
        print("Connecting to the database...")
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            db_name_result = connection.execute(text("SELECT current_database();")).scalar()
            print(f"Successfully connected to '{db_name_result}'.")
        
        # 複数のテーブルを作成する関数を呼び出す
        create_tables(engine)

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()