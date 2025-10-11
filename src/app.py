# src/app.py (改修後の完全版)

import os
from flask import Flask, render_template, request, Response, stream_with_context, jsonify
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import sessionmaker
from io import StringIO
import csv
import config

# create_table.py から MetaData クラスをインポートしてテーブル定義を再利用する
from scripts.create_table import MetaData

app = Flask(__name__)

def validate_token(token_str):
    """
    提供されたトークンを検証し、プラン情報を返します。
    戻り値: (プランタイプ, テーブル名) or (None, None)
    """
    if not token_str:
        return None, None

    engine = create_engine(config.DATABASE_URL)
    metadata = MetaData()
    metadata.reflect(bind=engine)
    tokens_table = metadata.tables['tokens']

    with engine.connect() as connection:
        stmt = select(tokens_table.c.plan_type).where(
            tokens_table.c.token == token_str,
            tokens_table.c.is_active == True
        )
        result = connection.execute(stmt).scalar_one_or_none()

    if result == 'bulk':
        return 'bulk', config.TABLE_NAME_FIXED
    elif result == 'subscription':
        return 'subscription', config.TABLE_NAME
    else:
        return None, None

@app.route('/')
def index():
    """メインページを表示します。"""
    return render_template('index.html')

@app.route('/plan_info', methods=['GET'])
def get_plan_info():
    """トークンに基づいてプラン情報を返します。"""
    token = request.args.get('token')
    plan_type, table_name = validate_token(token)

    if plan_type == 'bulk':
        engine = create_engine(config.DATABASE_URL)
        data_range_str = "データ未投入です (固定)" # デフォルト値
        try:
            with engine.connect() as connection:
                # stockdata_fixedテーブルから最小日付と最大日付を取得するクエリ
                query = text(f'SELECT MIN("日付"), MAX("日付") FROM public."{config.TABLE_NAME_FIXED}"')
                result = connection.execute(query).fetchone()
                if result and result[0] and result[1]:
                    start_date = result[0].strftime('%Y-%m-%d')
                    end_date = result[1].strftime('%Y-%m-%d')
                    data_range_str = f"{start_date} から {end_date} まで (固定)"
        except Exception as e:
            print(f"Error fetching data range for bulk plan: {e}")
            data_range_str = "期間の取得に失敗しました。"
        
        return jsonify({
            "status": "success",
            "plan_name": "買い切りプラン",
            "data_range": data_range_str # 動的に生成した文字列を使用
        })
    elif plan_type == 'subscription':
        return jsonify({
            "status": "success",
            "plan_name": "サブスクリプションプラン",
            "data_range": "2015-01-01 から 本日まで (毎日更新)"
        })
    else:
        return jsonify({
            "status": "error",
            "message": "無効なトークンです。"
        }), 401 # 401 Unauthorized

@app.route('/download', methods=['POST'])
def download():
    """トークンを検証し、株価データをCSVとしてストリーミングダウンロードします。"""
    token = request.form.get('token')
    
    # トークンを検証し、使用するテーブル名を取得
    plan_type, table_name = validate_token(token)
    if not plan_type:
        return "Error: Invalid or inactive token.", 401 # 401 Unauthorized

    # フォームから他のパラメータを取得
    tickers_str = request.form.get('tickers')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')

    # SQLクエリの構築
    base_query = f'SELECT * FROM public."{table_name}" WHERE 1=1'
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

    engine = create_engine(config.DATABASE_URL)

    def generate_csv():
        try:
            with engine.connect() as connection:
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
        except Exception as e:
            # エラー発生時もジェネレータを終了させる
            yield f"Error: {e}"
            return

    # ストリーミングレスポンスを返す
    response = Response(stream_with_context(generate_csv()), mimetype='text/csv')
    response.headers['Content-Disposition'] = 'attachment; filename=stock_data.csv'
    return response

if __name__ == '__main__':
    # この部分はローカルでの直接実行用。Gunicornからは使われない。
    app.run(host='0.0.0.0', port=5000, debug=True)