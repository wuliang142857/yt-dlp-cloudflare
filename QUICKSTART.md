# 快速开始指南

## 本地测试（使用代理）

如果您在本地开发并需要通过代理访问 YouTube，请按照以下步骤操作：

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 准备 cookies.txt（可选）

如果需要下载需要登录的视频，请准备 cookies.txt 文件。

### 3. 启动服务（使用代理）

```bash
# 使用 SOCKS5 代理（推荐）
python app.py --proxy socks5://127.0.0.1:50170

# 使用 SOCKS5 代理 + cookies
python app.py --cookies ../cookies.txt --proxy socks5://127.0.0.1:50170

# 完整配置
python app.py \
  --cookies ../cookies.txt \
  --proxy socks5://127.0.0.1:50170 \
  --port 8000
```

### 4. 测试 API

**健康检查**：
```bash
curl http://localhost:8000/health
```

**获取视频信息**：
```bash
curl -X POST http://localhost:8000/api/info \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

**下载视频**：
```bash
curl -X POST http://localhost:8000/api/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}' \
  -o video.mp4
```

## 常见代理配置

### SOCKS5 代理（推荐）

```bash
# 本地代理
python app.py --proxy socks5://127.0.0.1:1080

# 远程代理
python app.py --proxy socks5://proxy.example.com:1080

# 带认证的代理
python app.py --proxy socks5://username:password@127.0.0.1:1080
```

### HTTP 代理

```bash
# 本地代理
python app.py --proxy http://127.0.0.1:8080

# 远程代理
python app.py --proxy http://proxy.example.com:8080

# 带认证的代理
python app.py --proxy http://username:password@proxy.example.com:8080
```

## Docker 本地测试

### 构建镜像

```bash
cd backend
docker build -t youtube-downloader .
```

### 运行容器（使用代理）

```bash
# 使用宿主机代理（macOS/Linux）
docker run -p 8000:8000 \
  -e PROXY_URL=socks5://host.docker.internal:1080 \
  youtube-downloader

# 使用外部代理
docker run -p 8000:8000 \
  -e PROXY_URL=socks5://proxy.example.com:1080 \
  youtube-downloader

# 完整配置（cookies + 代理）
docker run -p 8000:8000 \
  -v $(pwd)/../cookies.txt:/app/cookies.txt \
  -e COOKIES_PATH=/app/cookies.txt \
  -e PROXY_URL=socks5://host.docker.internal:1080 \
  youtube-downloader
```

## 故障排查

### 问题 1：SSL 证书验证失败

**症状**：
```
ERROR: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed
```

**原因**：
使用代理时，代理服务器可能会对 HTTPS 流量进行中间人检查。

**解决方案**：
✅ **已自动修复**！应用已默认禁用 SSL 证书验证，您无需任何操作。

如果您看到这个错误，说明您使用的是旧版本代码。请重新启动应用：
```bash
python app.py --proxy socks5://127.0.0.1:50170
```

### 问题 2：无法连接到代理

**症状**：
```
ERROR: Unable to download video: Proxy connection failed
```

**解决方案**：
1. 检查代理服务器是否正在运行
2. 检查代理地址和端口是否正确
3. 检查防火墙是否阻止了连接
4. 如果使用 Docker，确保使用 `host.docker.internal` 访问宿主机代理

### 问题：SOCKS5 代理认证失败

**症状**：
```
ERROR: SOCKS5 authentication failed
```

**解决方案**：
1. 确认用户名和密码正确
2. 使用 URL 编码特殊字符（例如：`@` → `%40`）
3. 检查代理服务器是否启用了认证

### 问题：下载速度慢

**原因**：
- 代理服务器带宽限制
- 代理服务器地理位置较远

**解决方案**：
1. 尝试使用更快的代理服务器
2. 考虑使用本地代理
3. 如果可能，直接连接（不使用代理）

## 性能优化建议

### 1. 使用本地代理

本地代理（如 Clash、V2Ray）通常比远程代理更快：

```bash
python app.py --proxy socks5://127.0.0.1:7890
```

### 2. 选择合适的代理协议

- **SOCKS5**：最快，推荐用于视频下载
- **HTTP/HTTPS**：兼容性好，但可能较慢
- **SOCKS4**：不推荐（不支持 UDP 和认证）

### 3. 代理服务器位置

选择地理位置接近 YouTube 服务器的代理（通常是美国或欧洲）。

## 更多示例

### 下载多个视频（脚本示例）

```bash
#!/bin/bash
# download_videos.sh

# 配置
API_URL="http://localhost:8000/api/download"
VIDEOS=(
  "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
  "https://www.youtube.com/watch?v=9bZkp7q19f0"
  # 添加更多视频 URL
)

# 下载视频
for url in "${VIDEOS[@]}"; do
  echo "下载: $url"
  curl -X POST "$API_URL" \
    -H "Content-Type: application/json" \
    -d "{\"url\": \"$url\"}" \
    -o "video_$(date +%s).mp4"
  echo "完成！"
done
```

### Python 客户端示例

```python
import requests

API_URL = "http://localhost:8000"

def get_video_info(video_url):
    """获取视频信息"""
    response = requests.post(
        f"{API_URL}/api/info",
        json={"url": video_url}
    )
    return response.json()

def download_video(video_url, output_path):
    """下载视频"""
    response = requests.post(
        f"{API_URL}/api/download",
        json={"url": video_url},
        stream=True
    )

    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

# 使用示例
if __name__ == "__main__":
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    # 获取信息
    info = get_video_info(url)
    print(f"标题: {info['title']}")
    print(f"时长: {info['duration']} 秒")

    # 下载视频
    download_video(url, "video.mp4")
    print("下载完成！")
```

## 下一步

- 查看 [README.md](README.md) 了解完整的部署指南
- 查看 [CHANGELOG.md](CHANGELOG.md) 了解最新更新
- 遇到问题？查看 README.md 中的"故障排查"部分
