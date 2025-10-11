import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import yfinance as yf
import pandas as pd
import os
import time
import traceback
import sys
from datetime import datetime, timedelta, date # ★変更点: dateを追加インポート
from sqlalchemy import create_engine, text, inspect # ★変更点: inspectを追加インポート
import config

# ====================================================================
# 1. GLOBAL SETTINGS
# ====================================================================

# --- config.pyから読み込む設定 (環境に依存するもの) ---
DATABASE_URL = (
    f"postgresql+psycopg2://{config.DB_USER}:{config.DB_PASSWORD}@"
    f"{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}"
)
TABLE_NAME = "stockdata" # 保存先テーブル名を指定
script_dir = os.path.dirname(os.path.abspath(__file__))
TICKER_CSV_FILE = config.TICKER_CSV_FILE

# --- スクリプト内で直接定義するパラメータ (スクリプトの動作を決めるもの) ---
CHUNK_SIZE = 500
DELAY_SECONDS = 30

# ====================================================================
# 2. 関数定義
# ====================================================================

def get_latest_date_from_db(engine, table_name):
    """★追加: データベースから最新の日付を取得する関数"""
    try:
        inspector = inspect(engine)
        if not inspector.has_table(table_name):
            print(f"Table '{table_name}' does not exist. Running in full load mode.")
            return None # テーブルが存在しない場合はNoneを返す

        with engine.connect() as connection:
            result = connection.execute(text(f'SELECT MAX("日付") FROM public."{table_name}"'))
            latest_date = result.scalar()
            if latest_date:
                print(f"Latest date in DB is {latest_date}. Fetching data from the next day.")
                return latest_date
            else:
                print("Table is empty. Running in full load mode.")
                return None # テーブルが空の場合はNoneを返す
    except Exception as e:
        print(f"Error fetching latest date from DB: {e}. Running in full load mode.", file=sys.stderr)
        return None

def load_tickers_from_csv(file_path):
    """CSVからティッカーと会社名のDataFrameを読み込む。"""
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"ティッカーファイル '{file_path}' が見つかりません。")
        df = pd.read_csv(file_path)
        if "Ticker" not in df.columns or "銘柄名" not in df.columns:
            raise ValueError("CSVに 'Ticker' と '銘柄名' カラムが必要です。")
        df = df.rename(columns={"銘柄名": "CompanyName"})
        df["Ticker"] = df["Ticker"].dropna().astype(str)
        df["CompanyName"] = df["CompanyName"].dropna().astype(str)
        df = df.dropna(subset=["Ticker", "CompanyName"])
        print(f"{len(df)} 件のティッカー情報を {file_path} から読み込みました。")
        return df
    except Exception as e:
        print(f"エラー: ティッカーファイルの読み込み中に問題が発生しました: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


def create_db_engine():
    """PostgreSQLへの接続エンジンを作成する。"""
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            print(f"Successfully connected to PostgreSQL database '{config.DB_NAME}'.")
        return engine
    except Exception as e:
        print(f"Error connecting to PostgreSQL database: {e}", file=sys.stderr)
        traceback.print_exc()
        return None


def fetch_stock_data(tickers, start_date, end_date):
    """yfinanceからデータを1回で取得する。"""
    if not tickers:
        return pd.DataFrame()
    print(f"\nFetching data for {len(tickers)} tickers from {start_date} to {end_date}...")
    try:
        df = yf.download(
            tickers, start=start_date, end=end_date, group_by="ticker",
            auto_adjust=False, actions=True, threads=True, timeout=30,
        )
        print("Data fetching complete.")
        return df
    except Exception as e:
        print(f"An error occurred during data fetching: {e}", file=sys.stderr)
        return pd.DataFrame()


def process_data(df_raw, tickers):
    """未調整データと調整後データをメモリ上でマージし、最終的なDataFrameを作成する。"""
    print("Processing raw data...")
    all_processed_data = []
    for ticker in tickers:
        if ticker not in df_raw.columns.get_level_values(0): continue
        df_ticker = df_raw[ticker].copy().dropna(how="all").reset_index()
        if df_ticker.empty or "Close" not in df_ticker.columns: continue

        # 1. 分割係数を計算
        if 'Stock Splits' in df_ticker.columns and (df_ticker['Stock Splits'] > 0).any():
            df_ticker['split_factor'] = (df_ticker['Stock Splits'].replace(0, 1).iloc[::-1].cumprod().iloc[::-1])
        else:
            df_ticker['split_factor'] = 1

        # 2. 未調整データ（復元）と調整後データ（yfinanceから）を生成
        df_db = pd.DataFrame()
        df_db['日付'] = pd.to_datetime(df_ticker['Date'])
        df_db['始値'] = df_ticker['Open'] * df_ticker['split_factor']
        df_db['高値'] = df_ticker['High'] * df_ticker['split_factor']
        df_db['安値'] = df_ticker['Low'] * df_ticker['split_factor']
        df_db['終値'] = df_ticker['Close'] * df_ticker['split_factor']
        df_db['始値（調整後）'] = df_ticker['Open']
        df_db['高値（調整後）'] = df_ticker['High']
        df_db['安値（調整後）'] = df_ticker['Low']
        df_db['終値（調整後）'] = df_ticker['Close']
        df_db['出来高'] = df_ticker['Volume']
        
        # 3. データ型の整理と丸め処理
        price_cols = ['始値', '高値', '安値', '終値', '始値（調整後）', '高値（調整後）', '安値（調整後）', '終値（調整後）']
        df_db[price_cols] = df_db[price_cols].round(2)
        
        df_db['証券コード'] = ticker.replace(".T", "")
        df_db['日付'] = df_db['日付'].dt.date
        df_db['出来高'] = df_db['出来高'].astype('int64')
        
        all_processed_data.append(df_db.dropna(subset=['始値', '高値', '安値', '終値']))

    if not all_processed_data: return pd.DataFrame()
    final_df = pd.concat(all_processed_data, ignore_index=True)
    print(f"Processing complete. {len(final_df)} rows prepared.")
    return final_df


def upload_to_postgresql(engine, df, table_name):
    """DataFrameを指定されたテーブルにアップロードする (UPSERT処理)。"""
    if df.empty:
        print(f"No data to upload for table '{table_name}'.")
        return

    desired_order = [
        "証券コード", "銘柄名", "日付", "始値", "高値", "安値", "終値", 
        "始値（調整後）", "高値（調整後）", "安値（調整後）", "終値（調整後）", "出来高"
    ]
    df = df.reindex(columns=desired_order)
    
    temp_table_name = f"temp_{table_name}_{int(time.time())}"
    print(f"\nUploading {len(df)} rows to temporary table for '{table_name}': {temp_table_name}...")

    try:
        df.to_sql(temp_table_name, engine, index=False, if_exists='replace', schema='public')
        print("Upload to temporary table successful.")

        print(f"Merging data into main table: public.{table_name}...")
        conflict_keys = '"証券コード", "日付"'
        update_columns = [col for col in df.columns if col not in ['証券コード', '日付']]
        update_set_string = ", ".join([f'"{col}" = EXCLUDED."{col}"' for col in update_columns])
        insert_columns_string = ", ".join([f'"{col}"' for col in df.columns])

        merge_sql = f"""
        INSERT INTO public."{table_name}" ({insert_columns_string})
        SELECT {insert_columns_string} FROM public."{temp_table_name}"
        ON CONFLICT ({conflict_keys}) DO UPDATE SET
            {update_set_string};
        """
        
        with engine.begin() as connection:
            connection.execute(text(merge_sql))
            print(f"Merge operation for '{table_name}' completed successfully.")

    except Exception as e:
        print(f"Error during data upload to PostgreSQL for '{table_name}': {e}", file=sys.stderr)
        traceback.print_exc()
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP TABLE IF EXISTS public."{temp_table_name}"'))
            print(f"Temporary table {temp_table_name} deleted.")


# ====================================================================
# 3. メイン処理
# ====================================================================
def main():
    """スクリプトのメイン実行関数。"""
    start_time = time.time()
    print(f"--- Script started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

    # ★変更点: DBエンジンを先に作成し、最新日付を取得
    db_engine = create_db_engine()
    if not db_engine: sys.exit(1)
    
    latest_date_in_db = get_latest_date_from_db(db_engine, TABLE_NAME)

    if latest_date_in_db:
        # 差分更新モード: 最新日付の翌日からデータを取得
        start_date_obj = latest_date_in_db + timedelta(days=1)
        start_date_str = start_date_obj.strftime("%Y-%m-%d")
    else:
        # 全件取得モード: 2015年からデータを取得
        start_date_str = '2015-01-01'

    today = datetime.today()
    end_date_str = today.strftime("%Y-%m-%d")

    # ★変更点: データベースが既に最新の場合、処理を終了する
    if datetime.strptime(start_date_str, "%Y-%m-%d").date() > today.date():
        print("Database is already up to date. No new data to fetch. Exiting.")
        return

    print(f"Target Period: {start_date_str} to {end_date_str}")
    
    # ★変更点: DBエンジン作成処理は先頭に移動済み
    # db_engine = create_db_engine()
    # if not db_engine: sys.exit(1)

    ticker_df = load_tickers_from_csv(TICKER_CSV_FILE)

    # ★★★★★ テスト用にこの1行を追加 ★★★★★
    # 本番実行時はこの行をコメントアウト(#)または削除してください
    # ticker_df = pd.DataFrame([{"Ticker": "7984", "CompanyName": "コクヨ"}])
    
    if ticker_df.empty:
        print("Ticker list is empty. Exiting."); return

    yf_tickers = [f"{ticker}.T" for ticker in ticker_df["Ticker"]]
    # ★変更点: カラム名を 'CompanyName' から '銘柄名' に合わせる
    ticker_df = ticker_df.rename(columns={"Ticker": "証券コード", "CompanyName": "銘柄名"})
    
    ticker_chunks = [yf_tickers[i:i + CHUNK_SIZE] for i in range(0, len(yf_tickers), CHUNK_SIZE)]
    
    for i, ticker_chunk in enumerate(ticker_chunks):
        print(f"\n--- Processing Chunk {i+1}/{len(ticker_chunks)} ({len(ticker_chunk)} tickers) ---")
        raw_data = fetch_stock_data(ticker_chunk, start_date_str, end_date_str)
        
        if raw_data.empty:
            print("No data fetched for this chunk. Skipping.")
            continue

        processed_df = process_data(raw_data, ticker_chunk)
        
        if processed_df.empty:
            print("No data processed for this chunk. Skipping.")
            continue
            
        print("Merging company names for the current chunk...")
        # ★変更点: マージするカラム名を 'CompanyName' から '銘柄名' に合わせる
        final_dataframe = pd.merge(processed_df, ticker_df, on="証券コード", how="left")
        print("Merge complete.")

        if final_dataframe.empty:
            print("Final dataframe for this chunk is empty after merge. Skipping upload.")
            continue

        upload_to_postgresql(db_engine, final_dataframe, TABLE_NAME)

        if i < len(ticker_chunks) - 1:
            time.sleep(DELAY_SECONDS)

    end_time = time.time()
    print(f"\n--- All chunks processed. Process finished in {end_time - start_time:.2f} seconds ---")


if __name__ == "__main__":
    main()