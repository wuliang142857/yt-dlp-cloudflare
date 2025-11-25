from flask import Flask, request, send_file, Response, send_from_directory, after_this_request
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
import uuid
import threading
import time
import shutil
from pathlib import Path

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)  # 允许跨域请求

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def json_response(data, status=200):
    """返回 JSON 响应，支持中文"""
    return Response(
        json.dumps(data, ensure_ascii=False),
        status=status,
        mimetype='application/json; charset=utf-8'
    )

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

# ================ 下载任务管理 ================
# 使用基于文件的任务存储，解决多 worker 进程间数据共享问题
# 每个任务存储为独立的 JSON 文件：/tmp/yt-dlp-tasks/{task_id}.json

# 缓存目录
CACHE_DIR = os.environ.get('CACHE_DIR', '/tmp/yt-dlp-cache')
os.makedirs(CACHE_DIR, exist_ok=True)

# 任务文件目录
TASKS_DIR = os.path.join(CACHE_DIR, 'tasks')
os.makedirs(TASKS_DIR, exist_ok=True)

# 文件过期时间（秒）
FILE_EXPIRE_TIME = 5 * 60  # 5分钟

# 文件锁目录
LOCKS_DIR = os.path.join(CACHE_DIR, 'locks')
os.makedirs(LOCKS_DIR, exist_ok=True)

import fcntl

def get_task_file_path(task_id):
    """获取任务文件路径"""
    return os.path.join(TASKS_DIR, f'{task_id}.json')

def get_lock_file_path(task_id):
    """获取锁文件路径"""
    return os.path.join(LOCKS_DIR, f'{task_id}.lock')

def save_task(task_id, task_data):
    """保存任务数据到文件"""
    task_file = get_task_file_path(task_id)
    lock_file = get_lock_file_path(task_id)

    try:
        with open(lock_file, 'w') as lf:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            try:
                with open(task_file, 'w', encoding='utf-8') as f:
                    json.dump(task_data, f, ensure_ascii=False)
            finally:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
    except Exception as e:
        logger.error(f'保存任务数据失败: {task_id}, 错误: {e}')

def load_task(task_id):
    """从文件加载任务数据"""
    task_file = get_task_file_path(task_id)
    lock_file = get_lock_file_path(task_id)

    if not os.path.exists(task_file):
        return None

    try:
        with open(lock_file, 'w') as lf:
            fcntl.flock(lf.fileno(), fcntl.LOCK_SH)
            try:
                with open(task_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            finally:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
    except Exception as e:
        logger.error(f'加载任务数据失败: {task_id}, 错误: {e}')
        return None

def update_task(task_id, updates):
    """更新任务数据"""
    task_file = get_task_file_path(task_id)
    lock_file = get_lock_file_path(task_id)

    try:
        with open(lock_file, 'w') as lf:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            try:
                task_data = {}
                if os.path.exists(task_file):
                    with open(task_file, 'r', encoding='utf-8') as f:
                        task_data = json.load(f)

                task_data.update(updates)

                with open(task_file, 'w', encoding='utf-8') as f:
                    json.dump(task_data, f, ensure_ascii=False)
            finally:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
    except Exception as e:
        logger.error(f'更新任务数据失败: {task_id}, 错误: {e}')

def delete_task(task_id):
    """删除任务文件"""
    task_file = get_task_file_path(task_id)
    lock_file = get_lock_file_path(task_id)

    try:
        if os.path.exists(task_file):
            os.remove(task_file)
        if os.path.exists(lock_file):
            os.remove(lock_file)
    except Exception as e:
        logger.error(f'删除任务文件失败: {task_id}, 错误: {e}')

def get_all_task_ids():
    """获取所有任务ID"""
    try:
        task_files = os.listdir(TASKS_DIR)
        return [f[:-5] for f in task_files if f.endswith('.json')]
    except Exception as e:
        logger.error(f'获取任务列表失败: {e}')
        return []

def cleanup_expired_files():
    """清理过期的下载文件"""
    while True:
        try:
            time.sleep(30)  # 每30秒检查一次
            current_time = time.time()
            tasks_to_remove = []

            # 遍历所有任务文件
            for task_id in get_all_task_ids():
                task = load_task(task_id)
                if not task:
                    continue

                # 跳过正在下载的任务
                if task['status'] == 'downloading':
                    continue

                # 检查是否过期（下载完成后5分钟未被下载，或已被下载过）
                if task['status'] == 'completed':
                    # 已被下载过，删除文件和任务
                    if task.get('download_count', 0) > 0:
                        tasks_to_remove.append(task_id)
                        logger.info(f'任务 {task_id} 已被下载，准备清理')
                    # 超过5分钟未下载
                    elif task.get('downloaded_at') and (current_time - task['downloaded_at'] > FILE_EXPIRE_TIME):
                        tasks_to_remove.append(task_id)
                        logger.info(f'任务 {task_id} 已过期（5分钟未下载），准备清理')

                # 失败的任务也清理
                elif task['status'] == 'failed':
                    if current_time - task.get('created_at', 0) > FILE_EXPIRE_TIME:
                        tasks_to_remove.append(task_id)

            # 清理任务和文件
            for task_id in tasks_to_remove:
                task = load_task(task_id)
                if task:
                    filepath = task.get('filepath')
                    temp_dir = task.get('temp_dir')

                    # 删除文件
                    if filepath and os.path.exists(filepath):
                        try:
                            os.remove(filepath)
                            logger.info(f'已删除文件: {filepath}')
                        except Exception as e:
                            logger.error(f'删除文件失败: {e}')

                    # 删除临时目录
                    if temp_dir and os.path.exists(temp_dir):
                        try:
                            shutil.rmtree(temp_dir)
                            logger.info(f'已删除临时目录: {temp_dir}')
                        except Exception as e:
                            logger.error(f'删除临时目录失败: {e}')

                    # 删除任务文件
                    delete_task(task_id)
                    logger.info(f'已清理任务: {task_id}')

        except Exception as e:
            logger.error(f'清理线程错误: {e}')

# 启动清理线程
cleanup_thread = threading.Thread(target=cleanup_expired_files, daemon=True)
cleanup_thread.start()
logger.info('已启动文件清理线程')

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
    return json_response({'status': 'healthy'})

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
            return json_response({'error': '缺少 URL 参数'}, 400)

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
                return json_response({'error': '视频下载失败'}, 500)

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
        return json_response({'error': f'下载失败: {str(e)}'}, 400)
    except Exception as e:
        logger.error(f'服务器错误: {str(e)}')
        return json_response({'error': f'服务器错误: {str(e)}'}, 500)


# ================ 异步下载相关接口 ================

def download_video_task(task_id, video_url, format_id, subtitle_lang):
    """后台下载视频的任务函数"""
    temp_dir = None
    try:
        # 创建临时目录
        temp_dir = tempfile.mkdtemp(dir=CACHE_DIR)
        output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')

        # 更新任务状态
        update_task(task_id, {
            'temp_dir': temp_dir,
            'status': 'downloading'
        })

        # 进度回调函数
        def progress_hook(d):
            task = load_task(task_id)
            if not task:
                return

            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)

                if total > 0:
                    progress = (downloaded / total) * 100
                else:
                    progress = 0

                update_task(task_id, {
                    'progress': round(progress, 1),
                    'downloaded_bytes': downloaded,
                    'total_bytes': total,
                    'speed': d.get('speed', 0),
                    'eta': d.get('eta', 0),
                })
            elif d['status'] == 'finished':
                update_task(task_id, {
                    'progress': 100,
                    'status': 'processing'
                })

        # 配置 yt-dlp 选项
        ydl_opts = {
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'nocheckcertificate': True,
            'progress_hooks': [progress_hook],
        }

        # 设置格式
        if format_id:
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

        if PROXY_URL:
            ydl_opts['proxy'] = PROXY_URL

        # 下载视频
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)

            # 获取下载的文件路径
            if 'requested_downloads' in info:
                video_file = info['requested_downloads'][0]['filepath']
            else:
                video_file = ydl.prepare_filename(info)

            if not os.path.exists(video_file):
                raise Exception('视频文件不存在')

            video_title = info.get('title', 'video')
            video_ext = info.get('ext', 'mp4')
            file_size = os.path.getsize(video_file)

            clean_title = sanitize_filename(video_title)
            final_filename = f'{clean_title}.{video_ext}'
            final_filepath = video_file
            final_mimetype = 'video/mp4'

            # 检查是否有字幕文件需要打包
            subtitle_file = None
            if subtitle_lang:
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

                final_filename = zip_filename
                final_filepath = zip_path
                final_mimetype = 'application/zip'
                file_size = os.path.getsize(zip_path)

            # 更新任务状态为完成
            update_task(task_id, {
                'status': 'completed',
                'progress': 100,
                'filename': final_filename,
                'filepath': final_filepath,
                'filesize': file_size,
                'mimetype': final_mimetype,
                'downloaded_at': time.time(),
                'download_count': 0,
            })

            logger.info(f'任务 {task_id} 下载完成: {final_filename}, 大小: {file_size / 1024 / 1024:.2f} MB')

    except Exception as e:
        logger.error(f'任务 {task_id} 下载失败: {str(e)}')
        update_task(task_id, {
            'status': 'failed',
            'error': str(e),
        })
        # 清理临时目录
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except:
                pass


@app.route('/api/start-download', methods=['POST'])
def start_download():
    """
    启动后台下载任务
    请求体: {
        "url": "YouTube视频URL",
        "format_id": "格式ID（可选）",
        "subtitle": "字幕语言代码（可选）"
    }
    返回: { "task_id": "任务ID" }
    """
    try:
        data = request.get_json()

        if not data or 'url' not in data:
            return json_response({'error': '缺少 URL 参数'}, 400)

        video_url = data['url']
        format_id = data.get('format_id')
        subtitle_lang = data.get('subtitle')

        # 生成任务ID
        task_id = str(uuid.uuid4())

        # 初始化任务状态（保存到文件）
        save_task(task_id, {
            'status': 'pending',
            'progress': 0,
            'downloaded_bytes': 0,
            'total_bytes': 0,
            'speed': 0,
            'eta': 0,
            'filename': None,
            'filepath': None,
            'error': None,
            'created_at': time.time(),
            'downloaded_at': None,
            'download_count': 0,
            'temp_dir': None,
        })

        # 启动下载线程
        thread = threading.Thread(
            target=download_video_task,
            args=(task_id, video_url, format_id, subtitle_lang),
            daemon=True
        )
        thread.start()

        logger.info(f'启动下载任务: {task_id}, URL: {video_url}')

        return json_response({'task_id': task_id})

    except Exception as e:
        logger.error(f'启动下载任务失败: {str(e)}')
        return json_response({'error': f'启动下载失败: {str(e)}'}, 500)


@app.route('/api/progress/<task_id>', methods=['GET'])
def get_progress(task_id):
    """
    获取下载进度
    返回: {
        "status": "pending|downloading|processing|completed|failed",
        "progress": 0-100,
        "speed": 下载速度(bytes/s),
        "eta": 预计剩余时间(秒),
        "filename": 文件名(完成时),
        "filesize": 文件大小(完成时),
        "error": 错误信息(失败时)
    }
    """
    task = load_task(task_id)

    if not task:
        return json_response({'error': '任务不存在或已过期'}, 404)

    # 检查是否已被下载过
    if task['status'] == 'completed' and task.get('download_count', 0) > 0:
        return json_response({
            'status': 'expired',
            'error': '文件已被下载，不可重复下载'
        })

    response = {
        'status': task['status'],
        'progress': task['progress'],
    }

    if task['status'] == 'downloading':
        response.update({
            'downloaded_bytes': task.get('downloaded_bytes', 0),
            'total_bytes': task.get('total_bytes', 0),
            'speed': task.get('speed', 0),
            'eta': task.get('eta', 0),
        })
    elif task['status'] == 'completed':
        response.update({
            'filename': task.get('filename'),
            'filesize': task.get('filesize'),
        })
    elif task['status'] == 'failed':
        response['error'] = task.get('error', '未知错误')

    return json_response(response)


@app.route('/api/file/<task_id>', methods=['GET'])
def download_file(task_id):
    """
    下载已完成的文件
    文件下载后会被标记，稍后自动清理
    """
    task = load_task(task_id)

    if not task:
        return json_response({'error': '任务不存在或已过期'}, 404)

    if task['status'] != 'completed':
        return json_response({'error': '文件尚未准备好'}, 400)

    # 检查是否已被下载过
    if task.get('download_count', 0) > 0:
        return json_response({'error': '文件已被下载，不可重复下载'}, 410)

    filepath = task.get('filepath')
    filename = task.get('filename')
    mimetype = task.get('mimetype', 'application/octet-stream')

    if not filepath or not os.path.exists(filepath):
        return json_response({'error': '文件不存在'}, 404)

    # 标记为已下载
    update_task(task_id, {
        'download_count': task.get('download_count', 0) + 1
    })

    logger.info(f'用户下载文件: {task_id} - {filename}')

    return send_file(
        filepath,
        as_attachment=True,
        download_name=filename,
        mimetype=mimetype
    )


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
            return json_response({'error': '缺少 URL 参数'}, 400)

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
        return json_response({'error': f'获取信息失败: {str(e)}'}, 400)


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
