# YouTube 视频下载器

基于 yt-dlp 的 YouTube 视频下载工具，通过 Cloudflare Workers + Koyeb 部署，提供 Web 界面进行视频下载。

## 核心功能

- **视频下载**: 支持下载 YouTube 视频，可选择不同分辨率（720p/480p/360p/1080p/4K）
- **字幕下载**: 支持下载视频字幕（手动上传和自动生成的字幕），与视频一起打包为 zip
- **视频信息获取**: 获取视频标题、时长、上传者、观看次数等信息
- **格式选择**: 展示所有可用视频格式，显示分辨率、编码、文件大小、是否含音频
- **Cookie 支持**: 支持通过 cookies 文件或环境变量（Base64 编码）传入 YouTube cookies，用于下载受限视频
- **代理支持**: 支持配置 HTTP/SOCKS5 代理

## 架构

```
用户 -> Cloudflare Workers (CDN/反向代理) -> Koyeb (后端服务)
```

- **Cloudflare Workers**: 提供 CDN 加速和反向代理，处理 CORS
- **Koyeb**: 运行 Flask + yt-dlp 后端，执行实际的视频下载

## 部署方式

### 1. 部署后端到 Koyeb

#### 方式一：Docker 部署（推荐）

1. 构建并推送 Docker 镜像：
```bash
cd app
docker build -t your-registry/yt-dlp-api .
docker push your-registry/yt-dlp-api
```

2. 在 Koyeb 创建服务，配置环境变量：
   - `COOKIES_BASE64`: YouTube cookies 的 Base64 编码（可选）
   - `PROXY_URL`: 代理服务器地址（可选，如 `socks5://127.0.0.1:1080`）

#### 方式二：直接运行

```bash
cd app
pip install -r requirements.txt
python app.py --cookies /path/to/cookies.txt --port 8000
```

### 2. 部署 Cloudflare Workers

1. 安装 Wrangler CLI：
```bash
npm install -g wrangler
```

2. 修改 `worker/worker.js` 中的后端地址：
```javascript
const BACKEND_URL = 'https://your-koyeb-app.koyeb.app/';
```

3. 部署到 Cloudflare：
```bash
cd worker
wrangler login
wrangler deploy
```

### 3. 配置 Cookies（可选）

如果需要下载受限视频，可以通过以下方式配置 cookies：

**方式一：环境变量**
```bash
# 将 cookies.txt 转换为 Base64
cat cookies.txt | base64

# 设置环境变量 COOKIES_BASE64
```

**方式二：挂载文件**
```bash
# Docker 运行时挂载
docker run -v /path/to/cookies.txt:/app/cookies.txt your-image
```

## API 接口

### 获取视频信息
```
POST /api/info
Content-Type: application/json

{"url": "https://www.youtube.com/watch?v=xxx"}
```

### 下载视频
```
POST /api/download
Content-Type: application/json

{
  "url": "https://www.youtube.com/watch?v=xxx",
  "format_id": "136",      // 可选，格式ID
  "subtitle": "zh-Hans"    // 可选，字幕语言
}
```

### 健康检查
```
GET /health
```

## 目录结构

```
.
├── app/                    # 后端服务
│   ├── app.py             # Flask 主程序
│   ├── entrypoint.sh      # Docker 启动脚本
│   ├── Dockerfile         # Docker 构建文件
│   ├── requirements.txt   # Python 依赖
│   └── static/            # 前端静态文件
│       └── index.html     # Web 界面
└── worker/                # Cloudflare Workers
    ├── worker.js          # Worker 脚本
    └── wrangler.toml      # Wrangler 配置
```

---

<p align="center">
  <img src="https://img.shields.io/badge/Built%20with-AI-blueviolet?style=for-the-badge&logo=openai&logoColor=white" alt="Built with AI"/>
</p>

<p align="center">
  <b>🤖 这个工程全部是由 AI 来实现。</b>
</p>
