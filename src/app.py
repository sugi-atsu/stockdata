# src/app.py

import os
import secrets
from flask import Flask, render_template, request, Response, stream_with_context, jsonify, redirect, url_for, session
from sqlalchemy import create_engine, text, select, insert, update, delete
from datetime import datetime, date
from io import StringIO
import csv
import config

from scripts.create_table import MetaData

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback-secret-key-for-admin")

@app.context_processor
def inject_now():
    return {'now_date': date.today}

def get_db_engine():
    """データベースエンジンを返す"""
    return create_engine(config.DATABASE_URL)

def validate_token(token_str):
    """トークンを検証し、(プランタイプ, テーブル名) を返す"""
    if not token_str:
        return None, None
    engine = get_db_engine()
    metadata = MetaData()
    metadata.reflect(bind=engine)
    tokens_table = metadata.tables['tokens']
    with engine.connect() as connection:
        stmt = select(tokens_table.c.plan_type, tokens_table.c.expires_at).where(
            tokens_table.c.token == token_str,
            tokens_table.c.is_active == True
        )
        row = connection.execute(stmt).fetchone()
    
    if row:
        plan_type, expires_at = row
        # 有効期限のチェック
        if expires_at and expires_at < date.today():
            return None, None
            
        if plan_type == 'bulk':
            return 'bulk', config.TABLE_NAME_FIXED
        elif plan_type == 'subscription':
            return 'subscription', config.TABLE_NAME
        elif plan_type == 'trial':
            return 'trial', config.TABLE_NAME
            
    return None, None

def get_bulk_plan_date_range(engine):
    """買い切りプランの有効な日付範囲 (min, max) をDBから取得する"""
    try:
        with engine.connect() as connection:
            query = text(f'SELECT MIN("日付"), MAX("日付") FROM public."{config.TABLE_NAME_FIXED}"')
            result = connection.execute(query).fetchone()
            if result and result[0] and result[1]:
                return result[0], result[1] # dateオブジェクトを返す
    except Exception as e:
        print(f"Error fetching data range for bulk plan: {e}")
    return None, None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/trial')
def trial():
    return render_template('trial.html')

# --- 管理者用ルート ---

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == config.ADMIN_PASSWORD:
            session['is_admin'] = True
            return redirect(url_for('admin'))
        else:
            return render_template('admin.html', error="パスワードが違います")

    if not session.get('is_admin'):
        return render_template('admin.html', login_required=True)

    engine = get_db_engine()
    metadata = MetaData()
    metadata.reflect(bind=engine)
    tokens_table = metadata.tables['tokens']
    
    with engine.connect() as connection:
        # トークン一覧を取得
        stmt = select(tokens_table).order_by(tokens_table.c.created_at.desc())
        tokens = connection.execute(stmt).fetchall()
        
    return render_template('admin.html', tokens=tokens)

@app.route('/admin/issue', methods=['POST'])
def admin_issue():
    if not session.get('is_admin'):
        return "Unauthorized", 401
        
    user_name = request.form.get('user_name')
    user_email = request.form.get('user_email')
    plan_type = request.form.get('plan_type')
    expires_at_str = request.form.get('expires_at')
    
    expires_at = None
    if expires_at_str:
        expires_at = datetime.strptime(expires_at_str, '%Y-%m-%d').date()
        
    new_token = secrets.token_hex(16)
    
    engine = get_db_engine()
    metadata = MetaData()
    metadata.reflect(bind=engine)
    tokens_table = metadata.tables['tokens']
    
    with engine.connect() as connection:
        stmt = insert(tokens_table).values(
            token=new_token,
            plan_type=plan_type,
            user_name=user_name,
            user_email=user_email,
            expires_at=expires_at,
            is_active=True
        )
        connection.execute(stmt)
        connection.commit()
        
    return redirect(url_for('admin'))

@app.route('/admin/delete', methods=['POST'])
def admin_delete():
    if not session.get('is_admin'):
        return "Unauthorized", 401
        
    token_id = request.form.get('token_id')
    
    engine = get_db_engine()
    metadata = MetaData()
    metadata.reflect(bind=engine)
    tokens_table = metadata.tables['tokens']
    
    with engine.connect() as connection:
        stmt = delete(tokens_table).where(tokens_table.c.id == token_id)
        connection.execute(stmt)
        connection.commit()
        
    return redirect(url_for('admin'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('admin'))

# --- API ルート ---

@app.route('/plan_info', methods=['GET'])
def get_plan_info():
    """トークンに基づいてプラン情報を返す"""
    token = request.args.get('token')
    plan_type, _ = validate_token(token)

    if plan_type == 'bulk':
        engine = get_db_engine()
        min_date, max_date = get_bulk_plan_date_range(engine)
        if min_date and max_date:
            return jsonify({
                "status": "success",
                "plan_name": "買い切りプラン",
                "data_range": f"{min_date.strftime('%Y-%m-%d')} から {max_date.strftime('%Y-%m-%d')} まで (固定)",
                "min_date": min_date.strftime('%Y-%m-%d'),
                "max_date": max_date.strftime('%Y-%m-%d')
            })
        else:
            return jsonify({"status": "error", "message": "買い切りプランのデータ期間を取得できませんでした。"}), 500

    elif plan_type == 'subscription':
        return jsonify({
            "status": "success",
            "plan_name": "サブスクリプションプラン",
            "data_range": "2015-01-01 から 本日まで (毎日更新)"
        })
    elif plan_type == 'trial':
        return jsonify({
            "status": "success",
            "plan_name": "無料体験プラン",
            "data_range": "2025-01-01 から 2025-01-07 まで (お試し期間)",
            "min_date": "2025-01-01",
            "max_date": "2025-01-07"
        })
    else:
        return jsonify({"status": "error", "message": "無効なトークンです。"}), 401

@app.route('/download', methods=['POST'])
def download():
    """トークンを検証し、株価データをCSVとしてストリーミングダウンロードします。"""
    token = request.form.get('token')
    plan_type, table_name = validate_token(token)
    if not plan_type:
        return "Error: Invalid or inactive token.", 401

    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')
    
    engine = get_db_engine()

    # 買い切りプランの場合、サーバーサイドで厳格な期間チェックを行う
    if plan_type == 'bulk':
        min_valid_date, max_valid_date = get_bulk_plan_date_range(engine)
        if not min_valid_date or not max_valid_date:
            return "Error: Could not determine valid date range for this plan.", 500

        if start_date_str:
            try:
                req_start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                if req_start_date < min_valid_date:
                    return f"Error: Start date must be on or after {min_valid_date}.", 400
            except ValueError:
                return "Error: Invalid start_date format. Please use YYYY-MM-DD.", 400

        if end_date_str:
            try:
                req_end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                if req_end_date > max_valid_date:
                    return f"Error: End date must be on or before {max_valid_date}.", 400
            except ValueError:
                return "Error: Invalid end_date format. Please use YYYY-MM-DD.", 400

    # お試しプランの場合
    if plan_type == 'trial':
        start_date_str = "2025-01-01"
        end_date_str = "2025-01-07"

    tickers_str = request.form.get('tickers')
    base_query = f'SELECT * FROM public."{table_name}" WHERE 1=1'
    params = {}

    if tickers_str:
        tickers = [t.strip() for t in tickers_str.replace(',', ' ').replace('\n', ' ').split() if t.strip()]
        if tickers:
            base_query += ' AND "証券コード" IN :tickers'
            params['tickers'] = tuple(tickers)
    
    if start_date_str:
        base_query += ' AND "日付" >= :start_date'
        params['start_date'] = start_date_str
    if end_date_str:
        base_query += ' AND "日付" <= :end_date'
        params['end_date'] = end_date_str
        
    base_query += ' ORDER BY "証券コード", "日付"'

    def generate_csv():
        try:
            with engine.connect() as connection:
                stream_result = connection.execution_options(stream_results=True).execute(text(base_query), params)
                header = stream_result.keys()
                output = StringIO()
                writer = csv.writer(output)
                writer.writerow(header)
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)
                for row in stream_result:
                    writer.writerow(row)
                    yield output.getvalue()
                    output.seek(0)
                    output.truncate(0)
        except Exception as e:
            yield f"Error: {e}"
            return

    response = Response(stream_with_context(generate_csv()), mimetype='text/csv')
    response.headers['Content-Disposition'] = 'attachment; filename=stock_data.csv'
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)