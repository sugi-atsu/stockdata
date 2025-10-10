import os
from google.cloud import bigquery
from google.oauth2 import service_account

# --- 設定 ---
PROJECT_ID = "cellular-sylph-447307-f4"
DATASET_ID = "stock_data"

# テーブル名
TABLE_TO_DELETE = "daily_prices"  # 削除するテーブル
TABLE_TO_RENAME = "daily_prices_old_english"  # リネーム元のテーブル
FINAL_TABLE_NAME = "daily_prices" # リネーム先のテーブル名

# script_dir = os.path.dirname(os.path.abspath(__file__)) # この行は不要になる
# SERVICE_ACCOUNT_FILE = os.path.join(script_dir, "cellular-sylph-447307-f4-cc563add3ec8.json") # この行を削除

def main():
    """Renames a BigQuery table after deleting the destination table if it exists."""
    
    # ▼▼▼【ここから改修箇所】▼▼▼
    # 環境変数からサービスアカウントキーのJSONファイルのパスを取得
    service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not service_account_path:
        raise ValueError("環境変数 'GOOGLE_APPLICATION_CREDENTIALS' が設定されていません。")
    if not os.path.exists(service_account_path):
        raise FileNotFoundError(f"指定されたサービスアカウントファイルが見つかりません: {service_account_path}")

    print("Initializing BigQuery client...")
    credentials = service_account.Credentials.from_service_account_file(service_account_path)
    # ▲▲▲【ここまで改修箇所】▲▲▲

    client = bigquery.Client(credentials=credentials, project=PROJECT_ID)

    dataset_ref = client.dataset(DATASET_ID)

    # --- ステップ1: リネーム先のテーブルが存在すれば削除 ---
    table_to_delete_ref = dataset_ref.table(TABLE_TO_DELETE)
    try:
        client.get_table(table_to_delete_ref) # 存在確認
        print(f"Table '{TABLE_TO_DELETE}' exists. Deleting it...")
        client.delete_table(table_to_delete_ref)
        print(f"Table '{TABLE_TO_DELETE}' deleted successfully.")
    except Exception as e:
        print(f"Table '{TABLE_TO_DELETE}' does not exist or could not be deleted: {e}")

    # --- ステップ2: テーブルをリネーム ---
    # BigQueryクライアントライブラリには直接的なリネーム機能がないため、コピーと削除で実現します。
    
    source_table_ref = dataset_ref.table(TABLE_TO_RENAME)
    destination_table_ref = dataset_ref.table(FINAL_TABLE_NAME)

    print(f"Copying '{TABLE_TO_RENAME}' to '{FINAL_TABLE_NAME}'...")
    
    # コピージョブの設定
    job_config = bigquery.CopyJobConfig(
        write_disposition="WRITE_TRUNCATE" # コピー先が存在する場合は上書き
    )
    
    # コピージョブを開始
    copy_job = client.copy_table(
        source_table_ref,
        destination_table_ref,
        job_config=job_config
    )
    copy_job.result() # 完了を待つ
    
    print("Copy successful.")

    # --- ステップ3: 元のテーブルを削除 ---
    print(f"Deleting original table '{TABLE_TO_RENAME}'...")
    client.delete_table(source_table_ref)
    print(f"Original table '{TABLE_TO_RENAME}' deleted.")

    print(f"Successfully renamed '{TABLE_TO_RENAME}' to '{FINAL_TABLE_NAME}'.")


if __name__ == "__main__":
    main()