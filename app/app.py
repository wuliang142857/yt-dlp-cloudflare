from flask import Flask, request, send_file, jsonify, Response, send_from_directory
from flask_cors import CORS
import yt_dlp
import os
import sys
import tempfile
import logging
import argparse
import json
import re
import base64
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

def ensure_cookies():
    """
    从环境变量恢复 cookies（如果存在）

    检查 COOKIES_BASE64 环境变量，如果存在则解码并写入 cookies.txt
    这允许通过环境变量更新 cookies，而不需要重新构建镜像

    返回 cookies 文件路径（如果成功）或 None
    """
    # 默认 cookies 文件路径
    default_cookies_path = os.environ.get('COOKIES_FILE') or '/app/cookies.txt'

    # 检查是否有环境变量中的 base64 编码 cookies
    cookies_base64 = os.environ.get('COOKIES_BASE64')

    if cookies_base64:
        try:
            logger.info('🍪 从环境变量 COOKIES_BASE64 恢复 cookies...')

            # 解码 base64
            cookies_content = base64.b64decode(cookies_base64).decode('utf-8')

            # 统计 cookies 数量（非空行且非注释行）
            cookie_lines = [line for line in cookies_content.split('\n')
                          if line.strip() and not line.strip().startswith('#')]
            cookie_count = len(cookie_lines)

            # 确保目录存在
            cookies_dir = os.path.dirname(default_cookies_path)
            if cookies_dir and not os.path.exists(cookies_dir):
                os.makedirs(cookies_dir, exist_ok=True)

            # 写入文件
            with open(default_cookies_path, 'w', encoding='utf-8') as f:
                f.write(cookies_content)

            logger.info(f'✅ Cookies 已从环境变量恢复到 {default_cookies_path}')
            logger.info(f'📊 共 {cookie_count} 个 cookies')

            return default_cookies_path

        except Exception as e:
            logger.error(f'⚠️ 从环境变量恢复 cookies 失败: {e}')
            import traceback
            traceback.print_exc(file=sys.stderr)

    # 检查是否存在挂载的 cookies 文件
    if os.path.exists(default_cookies_path):
        logger.info(f'✅ 使用现有 cookies: {default_cookies_path}')
        return default_cookies_path

    logger.warning('⚠️ 未找到 cookies 文件，也没有 COOKIES_BASE64 环境变量')
    return None

# 全局变量：cookies 文件路径
# 优先从环境变量读取，用于 gunicorn 启动
# 启动时尝试从环境变量恢复 cookies
COOKIES_FILE = ensure_cookies()

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
    优先选择已包含音视频的单一格式，避免合并操作（大幅提升下载速度）
    优先 720p，其次 480p，然后 360p、1080p、最后最佳
    """
    # 优先选择已经包含音视频的格式，避免 ffmpeg 合并（速度提升 2-3 倍）
    return 'best[height<=720]/best[height<=480]/best[height<=360]/best[height<=1080]/best'

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
    请求体: {
        "url": "YouTube视频URL",
        "format_id": "格式ID（可选，不传则自动选择最佳）",
        "subtitle": "字幕语言代码（可选）"
    }
    """
    try:
        data = request.get_json()

        if not data or 'url' not in data:
            return jsonify({'error': '缺少 URL 参数'}), 400

        video_url = data['url']
        format_id = data.get('format_id')
        subtitle_lang = data.get('subtitle')

        logger.info(f'开始下载视频: {video_url}, 格式: {format_id}, 字幕: {subtitle_lang}')

        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')

        # 配置 yt-dlp 选项
        ydl_opts = {
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
            'nocheckcertificate': True,
        }

        # 设置格式：如果用户指定了 format_id 则使用，否则使用默认选择器
        if format_id:
            # 用户指定的格式可能没有音频，需要合并最佳音频
            ydl_opts['format'] = f'{format_id}+bestaudio/best/{format_id}'
            ydl_opts['merge_output_format'] = 'mp4'
        else:
            ydl_opts['format'] = get_format_selector()

        # 配置字幕下载
        if subtitle_lang:
            ydl_opts['writesubtitles'] = True
            ydl_opts['subtitleslangs'] = [subtitle_lang]
            ydl_opts['writeautomaticsub'] = True

        if COOKIES_FILE and os.path.exists(COOKIES_FILE):
            ydl_opts['cookiefile'] = COOKIES_FILE
            logger.info(f'使用 cookies 文件: {COOKIES_FILE}')
        else:
            logger.warning('未配置或未找到 cookies.txt 文件')

        if PROXY_URL:
            ydl_opts['proxy'] = PROXY_URL
            logger.info(f'使用代理: {PROXY_URL}')

        # 下载视频
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)

            # 获取下载的文件路径
            if 'requested_downloads' in info:
                video_file = info['requested_downloads'][0]['filepath']
            else:
                video_file = ydl.prepare_filename(info)

            if not os.path.exists(video_file):
                logger.error(f'视频文件不存在: {video_file}')
                return jsonify({'error': '视频下载失败'}), 500

            video_title = info.get('title', 'video')
            video_ext = info.get('ext', 'mp4')
            file_size = os.path.getsize(video_file)

            clean_title = sanitize_filename(video_title)
            final_filename = f'{clean_title}.{video_ext}'

            logger.info(f'视频下载成功: {video_title}, 大小: {file_size / 1024 / 1024:.2f} MB')

            # 检查是否有字幕文件需要打包
            subtitle_file = None
            if subtitle_lang:
                # 查找字幕文件
                for ext in ['vtt', 'srt', 'ass']:
                    sub_path = os.path.join(temp_dir, f'{os.path.splitext(os.path.basename(video_file))[0]}.{subtitle_lang}.{ext}')
                    if os.path.exists(sub_path):
                        subtitle_file = sub_path
                        break

            # 如果有字幕，打包成 zip
            if subtitle_file:
                import zipfile
                zip_filename = f'{clean_title}.zip'
                zip_path = os.path.join(temp_dir, zip_filename)

                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    zf.write(video_file, final_filename)
                    sub_ext = os.path.splitext(subtitle_file)[1]
                    zf.write(subtitle_file, f'{clean_title}.{subtitle_lang}{sub_ext}')

                logger.info(f'打包视频和字幕: {zip_filename}')
                return send_file(
                    zip_path,
                    as_attachment=True,
                    download_name=zip_filename,
                    mimetype='application/zip'
                )

            # 没有字幕，直接返回视频
            mimetype_map = {
                'mp4': 'video/mp4',
                'webm': 'video/webm',
                'mkv': 'video/x-matroska',
                'avi': 'video/x-msvideo',
                'mov': 'video/quicktime',
            }
            mimetype = mimetype_map.get(video_ext, 'application/octet-stream')

            return send_file(
                video_file,
                as_attachment=True,
                download_name=final_filename,
                mimetype=mimetype
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
    返回: 视频基本信息、可用格式列表、字幕列表
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
            'nocheckcertificate': True,
            'writesubtitles': True,
            'allsubtitles': True,
        }

        if COOKIES_FILE and os.path.exists(COOKIES_FILE):
            ydl_opts['cookiefile'] = COOKIES_FILE

        if PROXY_URL:
            ydl_opts['proxy'] = PROXY_URL

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)

            # 提取可用的视频格式
            formats = []
            seen_resolutions = set()

            for fmt in info.get('formats', []):
                # 只处理包含视频的格式
                if fmt.get('vcodec') == 'none':
                    continue

                height = fmt.get('height')
                if not height:
                    continue

                format_id = fmt.get('format_id')
                ext = fmt.get('ext', 'mp4')
                filesize = fmt.get('filesize') or fmt.get('filesize_approx')
                vcodec = fmt.get('vcodec', '')
                acodec = fmt.get('acodec', '')
                fps = fmt.get('fps')

                # 构建分辨率标签
                resolution_label = f"{height}p"
                if fps and fps > 30:
                    resolution_label += f" {fps}fps"

                # 判断是否包含音频
                has_audio = acodec and acodec != 'none'

                # 用于去重的 key（同分辨率+fps只保留一个）
                dedup_key = f"{height}_{fps}_{has_audio}"
                if dedup_key in seen_resolutions:
                    continue
                seen_resolutions.add(dedup_key)

                formats.append({
                    'format_id': format_id,
                    'height': height,
                    'resolution': resolution_label,
                    'ext': ext,
                    'filesize': filesize,
                    'has_audio': has_audio,
                    'vcodec': vcodec.split('.')[0] if vcodec else '',
                    'acodec': acodec.split('.')[0] if acodec else '',
                    'fps': fps,
                })

            # 按分辨率从高到低排序
            formats.sort(key=lambda x: (x['height'], x.get('fps') or 0), reverse=True)

            # 提取可用字幕
            subtitles = []
            subtitle_data = info.get('subtitles', {})
            auto_captions = info.get('automatic_captions', {})

            # 手动上传的字幕
            for lang, subs in subtitle_data.items():
                if subs:
                    subtitles.append({
                        'lang': lang,
                        'name': get_language_name(lang),
                        'auto': False,
                    })

            # 自动生成的字幕
            for lang, subs in auto_captions.items():
                if subs and lang not in subtitle_data:
                    subtitles.append({
                        'lang': lang,
                        'name': get_language_name(lang) + ' (自动生成)',
                        'auto': True,
                    })

            result = {
                'title': info.get('title'),
                'duration': info.get('duration'),
                'thumbnail': info.get('thumbnail'),
                'uploader': info.get('uploader'),
                'view_count': info.get('view_count'),
                'description': info.get('description', '')[:200],
                'formats': formats,
                'subtitles': subtitles,
            }

            return Response(
                json.dumps(result, ensure_ascii=False),
                mimetype='application/json; charset=utf-8'
            )

    except Exception as e:
        logger.error(f'获取视频信息失败: {str(e)}')
        return jsonify({'error': f'获取信息失败: {str(e)}'}), 400


def get_language_name(lang_code):
    """将语言代码转换为可读名称"""
    lang_map = {
        'zh-Hans': '中文(简体)',
        'zh-Hant': '中文(繁体)',
        'zh-CN': '中文(简体)',
        'zh-TW': '中文(繁体)',
        'zh': '中文',
        'en': '英语',
        'en-US': '英语(美国)',
        'en-GB': '英语(英国)',
        'ja': '日语',
        'ko': '韩语',
        'es': '西班牙语',
        'fr': '法语',
        'de': '德语',
        'ru': '俄语',
        'pt': '葡萄牙语',
        'it': '意大利语',
        'ar': '阿拉伯语',
        'hi': '印地语',
        'th': '泰语',
        'vi': '越南语',
        'id': '印尼语',
        'ms': '马来语',
        'tr': '土耳其语',
        'pl': '波兰语',
        'nl': '荷兰语',
        'sv': '瑞典语',
        'fi': '芬兰语',
        'no': '挪威语',
        'da': '丹麦语',
        'cs': '捷克语',
        'hu': '匈牙利语',
        'el': '希腊语',
        'he': '希伯来语',
        'uk': '乌克兰语',
        'ro': '罗马尼亚语',
    }
    return lang_map.get(lang_code, lang_code)

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
