# ベースイメージをPython 3.12に変更
FROM python:3.12-slim

# 作業ディレクトリを設定
WORKDIR /app

# 依存ライブラリをインストール
# requirements.txtを先にコピーすることで、ソースコード変更時の再インストールを防ぎキャッシュを有効活用
COPY .docker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのソースコードをコピー
# docker-compose.ymlのcontextで指定されたディレクトリ(プロジェクトルート)からsrcディレクトリをコピー
COPY ./src .

# コンテナが起動したときに実行されるコマンド
# WSGIサーバーであるgunicornを使い、外部(0.0.0.0)からポート5000でアクセス可能にする
# app.pyファイル内のappインスタンスを起動
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]