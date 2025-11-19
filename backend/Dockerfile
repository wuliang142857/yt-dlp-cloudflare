FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（ffmpeg 用于视频处理）
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 复制 requirements.txt
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app.py .

# 复制 cookies.txt（如果存在）
COPY cookies.txt /app/cookies.txt 2>/dev/null || true

# 暴露端口
EXPOSE 8000

# 使用 gunicorn 运行应用
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "300", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
