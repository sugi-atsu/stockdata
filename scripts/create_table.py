# create_table.py

import os
import sys
from sqlalchemy import create_engine, text, inspect, Table, Column, String, MetaData, Date
# 修正点: Float と BigInteger を sqlalchemy からインポートする
from sqlalchemy import Float, BigInteger 

# このスクリプトの親ディレクトリ(/app)を検索パスに追加
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# configモジュールをインポート
import config

def create_stock_table(engine, table_name):
    """
    指定されたエンジンを使用して、株式データ用のテーブルを作成または検証します。
    """
    try:
        # メタデータを定義
        metadata = MetaData()

        # テーブルのスキーマ（構造）を定義
        stock_table = Table(
            table_name,
            metadata,
            Column("証券コード", String(10), primary_key=True),
            Column("銘柄名", String(255)),
            Column("日付", Date, primary_key=True),
            # 修正点: 株価関連のデータ型を Float に変更
            Column("始値", Float),
            Column("高値", Float),
            Column("安値", Float),
            Column("終値", Float),
            Column("始値（調整後）", Float),
            Column("高値（調整後）", Float),
            Column("安値（調整後）", Float),
            Column("終値（調整後）", Float),
            # 修正点: 出来高のデータ型を BigInteger に変更
            Column("出来高", BigInteger)
        )

        # データベースにテーブルを作成する（存在しない場合のみ）
        print("Executing CREATE TABLE statement...")
        metadata.create_all(engine, checkfirst=True)
        
        # テーブルが存在するかを再確認
        inspector = inspect(engine)
        if inspector.has_table(table_name):
            print(f"Table '{table_name}' created successfully or already exists.")
        else:
            print(f"Failed to create table '{table_name}'.")
            
    except Exception as e:
        print(f"An error occurred during table creation: {e}")

def main():
    """
    メインの実行関数
    """
    DATABASE_URL = config.DATABASE_URL
    TABLE_NAME = config.TABLE_NAME

    try:
        print("Connecting to the database...")
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            db_name_result = connection.execute(text("SELECT current_database();")).scalar()
            print(f"Successfully connected to '{db_name_result}'.")
        
        create_stock_table(engine, TABLE_NAME)

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()