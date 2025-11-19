FROM python:3.11-slim-bookworm 

# 设置工作目录
WORKDIR /app

# 安装系统依赖（ffmpeg 用于视频处理）
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources && \ 
    apt update && apt-get install -y \
    ffmpeg && \
    apt clean && \
	apt autoclean && \
	apt autoremove --yes && \
	rm -rf /var/lib/{apt,dpkg,cache,log}/

# 复制 requirements.txt
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app.py .

COPY cookies.txt . 

# 暴露端口
EXPOSE 8000

# 使用 gunicorn 运行应用
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "300", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
