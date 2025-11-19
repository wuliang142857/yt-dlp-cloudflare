#!/bin/bash
# Entrypoint script for YouTube Downloader API

# 默认 cookies 文件路径
COOKIES_PATH="${COOKIES_PATH:-/app/cookies.txt}"

# 检查 cookies 文件是否存在
if [ -f "$COOKIES_PATH" ]; then
    echo "使用 cookies 文件: $COOKIES_PATH"
    export COOKIES_FILE="$COOKIES_PATH"
else
    echo "警告: Cookies 文件不存在: $COOKIES_PATH"
    echo "将在没有 cookies 的情况下运行"
    export COOKIES_FILE=""
fi

# 配置代理（可选）
if [ -n "$PROXY_URL" ]; then
    echo "使用代理: $PROXY_URL"
    export PROXY_URL="$PROXY_URL"
else
    echo "未配置代理，将直接连接"
fi

# 启动 gunicorn
exec gunicorn --bind 0.0.0.0:8000 \
    --workers 2 \
    --timeout 300 \
    --access-logfile - \
    --error-logfile - \
    app:app
