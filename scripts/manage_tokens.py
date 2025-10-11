# scripts/manage_tokens.py (新規作成)

import os
import sys
import argparse
import secrets
from sqlalchemy import create_engine, text, select, insert, update
from sqlalchemy.orm import sessionmaker

# このスクリプトの親ディレクトリ(/app)を検索パスに追加
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import config
# create_table.py から MetaData クラスをインポートしてテーブル定義を再利用する
from scripts.create_table import MetaData

def generate_token():
    """安全なランダムトークンを生成します。"""
    return secrets.token_hex(16)

def add_token(engine, plan_type):
    """新しいトークンをDBに追加します。"""
    new_token_str = generate_token()
    
    metadata = MetaData()
    metadata.reflect(bind=engine)
    tokens_table = metadata.tables['tokens']

    try:
        with engine.connect() as connection:
            stmt = insert(tokens_table).values(token=new_token_str, plan_type=plan_type, is_active=True)
            connection.execute(stmt)
            connection.commit() # 変更をDBに確定させる
        
        print("="*40)
        print("✅ New Token Generated Successfully!")
        print(f"  Plan: {plan_type}")
        print(f"  Token: {new_token_str}")
        print("="*40)
    except Exception as e:
        print(f"❌ Error adding token: {e}")

def set_token_status(engine, token_str, is_active):
    """指定されたトークンの有効/無効ステータスを設定します。"""
    metadata = MetaData()
    metadata.reflect(bind=engine)
    tokens_table = metadata.tables['tokens']
    
    status_str = "ACTIVATED" if is_active else "DEACTIVATED"

    try:
        with engine.connect() as connection:
            stmt = update(tokens_table).where(tokens_table.c.token == token_str).values(is_active=is_active)
            result = connection.execute(stmt)
            connection.commit()

            if result.rowcount == 0:
                print(f"❌ Error: Token '{token_str}' not found.")
            else:
                print(f"✅ Token '{token_str}' has been {status_str}.")
    except Exception as e:
        print(f"❌ Error updating token status: {e}")

def list_tokens(engine):
    """DBに登録されているすべてのトークンを一覧表示します。"""
    metadata = MetaData()
    metadata.reflect(bind=engine)
    tokens_table = metadata.tables['tokens']
    
    try:
        with engine.connect() as connection:
            stmt = select(tokens_table).order_by(tokens_table.c.id)
            results = connection.execute(stmt).fetchall()
        
        if not results:
            print("No tokens found in the database.")
            return

        print("{:<35} {:<15} {:<10}".format("Token", "Plan Type", "Is Active"))
        print("-" * 65)
        for row in results:
            # rowオブジェクトから属性名で値を取得する
            print("{:<35} {:<15} {:<10}".format(row.token, row.plan_type, str(row.is_active)))
    except Exception as e:
        print(f"❌ Error listing tokens: {e}")

def main():
    """コマンドライン引数を解釈して、対応する関数を実行します。"""
    parser = argparse.ArgumentParser(description="Manage authentication tokens for StockData app.")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # 'add' コマンドの設定
    parser_add = subparsers.add_parser("add", help="Add a new token.")
    parser_add.add_argument("plan_type", choices=['bulk', 'subscription'], help="The plan type for the new token ('bulk' or 'subscription').")

    # 'deactivate' コマンドの設定
    parser_deactivate = subparsers.add_parser("deactivate", help="Deactivate a token.")
    parser_deactivate.add_argument("token", help="The token string to deactivate.")
    
    # 'activate' コマンドの設定
    parser_activate = subparsers.add_parser("activate", help="Reactivate a token.")
    parser_activate.add_argument("token", help="The token string to activate.")

    # 'list' コマンドの設定
    subparsers.add_parser("list", help="List all tokens in the database.")

    args = parser.parse_args()
    
    try:
        engine = create_engine(config.DATABASE_URL)

        if args.command == "add":
            add_token(engine, args.plan_type)
        elif args.command == "deactivate":
            set_token_status(engine, args.token, is_active=False)
        elif args.command == "activate":
            set_token_status(engine, args.token, is_active=True)
        elif args.command == "list":
            list_tokens(engine)
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()