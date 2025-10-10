# app.py
# FINAL_ATTEMPT - THIS IS THE ABSOLUTELY CLEAN VERSION

import os
from flask import Flask, render_template, request, Response, stream_with_context
from sqlalchemy import create_engine, text
# import pandas as pd # pandasはもう使わない
from io import StringIO
import csv # 標準のcsvライブラリを使う
import config

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    print("Creating database engine...")
    try:
        engine = create_engine(config.DATABASE_URL)
    except Exception as e:
        print(f"Failed to create database engine: {e}")
        return "Database engine creation failed.", 500
    
    tickers_str = request.form.get('tickers')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')

    base_query = f'SELECT * FROM public."{config.TABLE_NAME}" WHERE 1=1'
    params = {}

    if tickers_str:
        tickers = [t.strip() for t in tickers_str.replace(',', ' ').replace('\n', ' ').split() if t.strip()]
        if tickers:
            base_query += ' AND "証券コード" IN :tickers'
            params['tickers'] = tuple(tickers)

    if start_date:
        base_query += ' AND "日付" >= :start_date'
        params['start_date'] = start_date

    if end_date:
        base_query += ' AND "日付" <= :end_date'
        params['end_date'] = end_date
        
    base_query += ' ORDER BY "証券コード", "日付"'

    def generate_csv():
        try:
            with engine.connect() as connection:
                print("Successfully connected. Executing stream query.")
                # サーバーサイドカーソルを使ってメモリ効率の良いクエリを実行
                stream_result = connection.execution_options(stream_results=True).execute(text(base_query), params)
                
                # ヘッダー行を書き出す
                header = stream_result.keys()
                output = StringIO()
                writer = csv.writer(output)
                writer.writerow(header)
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)

                # データ行を少しずつ書き出す
                for row in stream_result:
                    writer.writerow(row)
                    yield output.getvalue()
                    output.seek(0)
                    output.truncate(0)
                
                print("Stream query finished.")

        except Exception as e:
            print(f"An error occurred during CSV generation: {e}")
            # エラー発生時もジェネレータを終了させる
            yield f"Error: {e}"
            return

    # ストリーミングレスポンスを返す
    response = Response(stream_with_context(generate_csv()), mimetype='text/csv')
    response.headers['Content-Disposition'] = 'attachment; filename=stock_data.csv'
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)), debug=True)