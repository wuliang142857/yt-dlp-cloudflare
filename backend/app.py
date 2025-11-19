from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import yt_dlp
import os
import tempfile
import logging
from pathlib import Path

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 视频质量优先级：720p > 480p > 360p > 1080p > 4K
QUALITY_PRIORITY = ['720', '480', '360', '1080', '2160']

def get_format_selector():
    """
    根据优先级返回格式选择器
    优先选择 720p，其次 480p，然后 360p、1080p、最后 4K
    """
    # 构建格式选择字符串，按优先级选择最佳视频+音频
    return f'bestvideo[height<=720]+bestaudio/bestvideo[height<=480]+bestaudio/bestvideo[height<=360]+bestaudio/bestvideo[height<=1080]+bestaudio/bestvideo+bestaudio/best'

@app.route('/')
def index():
    """健康检查端点"""
    return jsonify({
        'status': 'ok',
        'message': 'YouTube Downloader API is running',
        'version': '1.0.0'
    })

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

        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')

        # 检查 cookies 文件
        cookies_file = '/app/cookies.txt' if os.path.exists('/app/cookies.txt') else None
        if not cookies_file:
            # 本地开发环境
            cookies_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cookies.txt')
            if not os.path.exists(cookies_file):
                cookies_file = None
                logger.warning('未找到 cookies.txt 文件')

        # 配置 yt-dlp 选项
        ydl_opts = {
            'format': get_format_selector(),
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
            'merge_output_format': 'mp4',  # 合并为 mp4 格式
        }

        # 如果有 cookies 文件，添加到配置
        if cookies_file:
            ydl_opts['cookiefile'] = cookies_file
            logger.info(f'使用 cookies 文件: {cookies_file}')

        # 下载视频
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # 获取视频信息
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

            # 获取视频信息
            video_title = info.get('title', 'video')
            video_ext = info.get('ext', 'mp4')
            file_size = os.path.getsize(video_file)

            logger.info(f'视频下载成功: {video_title}, 大小: {file_size / 1024 / 1024:.2f} MB')

            # 发送文件
            return send_file(
                video_file,
                as_attachment=True,
                download_name=f'{video_title}.{video_ext}',
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

        # 检查 cookies 文件
        cookies_file = '/app/cookies.txt' if os.path.exists('/app/cookies.txt') else None
        if not cookies_file:
            cookies_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cookies.txt')
            if not os.path.exists(cookies_file):
                cookies_file = None

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }

        if cookies_file:
            ydl_opts['cookiefile'] = cookies_file

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)

            return jsonify({
                'title': info.get('title'),
                'duration': info.get('duration'),
                'thumbnail': info.get('thumbnail'),
                'uploader': info.get('uploader'),
                'view_count': info.get('view_count'),
                'description': info.get('description', '')[:200],  # 限制描述长度
            })

    except Exception as e:
        logger.error(f'获取视频信息失败: {str(e)}')
        return jsonify({'error': f'获取信息失败: {str(e)}'}), 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
