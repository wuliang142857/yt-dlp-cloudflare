from flask import Flask, request, send_file, jsonify, Response, send_from_directory
from flask_cors import CORS
import yt_dlp
import os
import tempfile
import logging
import argparse
import json
import re
from pathlib import Path

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)  # 允许跨域请求

# 配置 Flask JSON 输出，禁用 ASCII 编码（支持中文等非 ASCII 字符）
app.config['JSON_AS_ASCII'] = False
app.config['JSON_SORT_KEYS'] = False  # 保持 JSON 键的原始顺序

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 视频质量优先级：720p > 480p > 360p > 1080p > 4K
QUALITY_PRIORITY = ['720', '480', '360', '1080', '2160']

# 全局变量：cookies 文件路径
# 优先从环境变量读取，用于 gunicorn 启动
COOKIES_FILE = os.environ.get('COOKIES_FILE', '/app/cookies.txt')

# 初始化时检查 cookies 文件
if COOKIES_FILE and os.path.exists(COOKIES_FILE):
    logger.info(f'已配置 cookies 文件: {COOKIES_FILE}')
elif COOKIES_FILE:
    logger.warning(f'Cookies 文件不存在: {COOKIES_FILE}，将在没有 cookies 的情况下运行')
    COOKIES_FILE = None
else:
    logger.warning('未配置 cookies 文件，将在没有 cookies 的情况下运行')
    COOKIES_FILE = None

# 全局变量：代理设置
# 优先从环境变量读取，用于 gunicorn 启动
PROXY_URL = os.environ.get('PROXY_URL', None)

# 初始化时检查代理设置
if PROXY_URL:
    logger.info(f'已配置代理: {PROXY_URL}')
else:
    logger.info('未配置代理，将直接连接')

def sanitize_filename(filename, max_length=100):
    """
    清理文件名，移除非法字符
    """
    # 移除或替换非法字符
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # 移除控制字符
    filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)
    # 去除首尾空格
    filename = filename.strip()
    # 限制长度（考虑到扩展名 .mp4 占 4 个字符）
    if len(filename) > max_length - 4:
        filename = filename[:max_length - 4]
    # 如果清理后为空，使用默认名称
    if not filename:
        filename = 'video'
    return filename

def get_format_selector():
    """
    根据优先级返回格式选择器
    优先选择 720p，其次 480p，然后 360p、1080p、最后 4K
    """
    # 构建格式选择字符串，按优先级选择最佳视频+音频
    return f'bestvideo[height<=720]+bestaudio/bestvideo[height<=480]+bestaudio/bestvideo[height<=360]+bestaudio/bestvideo[height<=1080]+bestaudio/bestvideo+bestaudio/best'

@app.route('/')
def index():
    """返回前端页面"""
    return send_from_directory('static', 'index.html')

@app.route('/health')
def health():
    """Koyeb 健康检查"""
    return jsonify({'status': 'healthy'}), 200

@app.route('/api/download', methods=['POST'])
def download_video():
    """
    下载 YouTube 视频
    请求体: {"url": "YouTube视频URL"}
    """
    try:
        data = request.get_json()

        if not data or 'url' not in data:
            return jsonify({'error': '缺少 URL 参数'}), 400

        video_url = data['url']
        logger.info(f'开始下载视频: {video_url}')

        # 配置 yt-dlp 选项用于获取视频信息
        info_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'nocheckcertificate': True,
        }

        # 如果有 cookies 文件，添加到配置
        if COOKIES_FILE and os.path.exists(COOKIES_FILE):
            info_opts['cookiefile'] = COOKIES_FILE
            logger.info(f'使用 cookies 文件: {COOKIES_FILE}')

        # 如果有代理配置，添加到选项
        if PROXY_URL:
            info_opts['proxy'] = PROXY_URL
            logger.info(f'使用代理: {PROXY_URL}')

        # 先获取视频信息以获取标题
        video_title = 'video'
        with yt_dlp.YoutubeDL(info_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            video_title = info.get('title', 'video')
            logger.info(f'获取视频标题: {video_title}')

        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')

        # 配置 yt-dlp 选项用于下载
        ydl_opts = {
            'format': get_format_selector(),
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
            'merge_output_format': 'mp4',  # 合并为 mp4 格式
            'nocheckcertificate': True,  # 禁用 SSL 证书验证（解决代理证书问题）
        }

        # 如果有 cookies 文件，添加到配置
        if COOKIES_FILE and os.path.exists(COOKIES_FILE):
            ydl_opts['cookiefile'] = COOKIES_FILE

        # 如果有代理配置，添加到选项
        if PROXY_URL:
            ydl_opts['proxy'] = PROXY_URL

        # 下载视频
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # 获取视频信息并下载
            info = ydl.extract_info(video_url, download=True)

            # 获取下载的文件路径
            if 'requested_downloads' in info:
                video_file = info['requested_downloads'][0]['filepath']
            else:
                # 如果没有 requested_downloads，尝试根据模板构建文件名
                video_file = ydl.prepare_filename(info)

            if not os.path.exists(video_file):
                logger.error(f'视频文件不存在: {video_file}')
                return jsonify({'error': '视频下载失败'}), 500

            video_ext = info.get('ext', 'mp4')
            file_size = os.path.getsize(video_file)

            # 清理文件名（使用之前获取的标题）
            clean_title = sanitize_filename(video_title)
            final_filename = f'{clean_title}.{video_ext}'

            logger.info(f'视频下载成功: {video_title}, 大小: {file_size / 1024 / 1024:.2f} MB')

            # 发送文件
            return send_file(
                video_file,
                as_attachment=True,
                download_name=final_filename,
                mimetype='video/mp4'
            )

    except yt_dlp.utils.DownloadError as e:
        logger.error(f'下载错误: {str(e)}')
        return jsonify({'error': f'下载失败: {str(e)}'}), 400
    except Exception as e:
        logger.error(f'服务器错误: {str(e)}')
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500

@app.route('/api/info', methods=['POST'])
def get_video_info():
    """
    获取视频信息（不下载）
    请求体: {"url": "YouTube视频URL"}
    """
    try:
        data = request.get_json()

        if not data or 'url' not in data:
            return jsonify({'error': '缺少 URL 参数'}), 400

        video_url = data['url']
        logger.info(f'获取视频信息: {video_url}')

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'nocheckcertificate': True,  # 禁用 SSL 证书验证（解决代理证书问题）
        }

        # 如果有 cookies 文件，添加到配置
        if COOKIES_FILE and os.path.exists(COOKIES_FILE):
            ydl_opts['cookiefile'] = COOKIES_FILE

        # 如果有代理配置，添加到选项
        if PROXY_URL:
            ydl_opts['proxy'] = PROXY_URL

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)

            result = {
                'title': info.get('title'),
                'duration': info.get('duration'),
                'thumbnail': info.get('thumbnail'),
                'uploader': info.get('uploader'),
                'view_count': info.get('view_count'),
                'description': info.get('description', '')[:200],  # 限制描述长度
            }

            # 使用 json.dumps 显式设置 ensure_ascii=False 以支持中文
            return Response(
                json.dumps(result, ensure_ascii=False),
                mimetype='application/json; charset=utf-8'
            )

    except Exception as e:
        logger.error(f'获取视频信息失败: {str(e)}')
        return jsonify({'error': f'获取信息失败: {str(e)}'}), 400

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='YouTube Downloader API Server')
    parser.add_argument(
        '--cookies',
        type=str,
        default='/app/cookies.txt',
        help='cookies.txt 文件路径 (默认: /app/cookies.txt)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=None,
        help='服务器端口 (默认: 从环境变量 PORT 读取，或 8000)'
    )
    parser.add_argument(
        '--proxy',
        type=str,
        default=None,
        help='代理服务器地址 (例如: socks5://127.0.0.1:1080 或 http://proxy.example.com:8080)'
    )
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()

    # 设置全局 cookies 文件路径
    COOKIES_FILE = args.cookies
    if os.path.exists(COOKIES_FILE):
        logger.info(f'已配置 cookies 文件: {COOKIES_FILE}')
    else:
        logger.warning(f'Cookies 文件不存在: {COOKIES_FILE}，将在没有 cookies 的情况下运行')

    # 设置全局代理
    if args.proxy:
        PROXY_URL = args.proxy
        logger.info(f'已配置代理: {PROXY_URL}')
    else:
        logger.info('未配置代理，将直接连接')

    # 确定端口
    port = args.port if args.port else int(os.environ.get('PORT', 8000))
    logger.info(f'启动服务器，监听端口: {port}')

    app.run(host='0.0.0.0', port=port, debug=False)
