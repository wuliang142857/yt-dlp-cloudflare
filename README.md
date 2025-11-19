# YouTube 视频下载器

基于 Cloudflare Workers + Koyeb 的 YouTube 视频下载服务，解决中国访问问题。

## 架构说明

```
用户（中国） → Cloudflare Workers（代理层，国内可访问）→ Koyeb（后端，运行 yt-dlp）
```

- **前端**: Cloudflare Pages（静态页面托管）
- **代理层**: Cloudflare Workers（转发请求）
- **后端**: Koyeb（Flask + yt-dlp，处理视频下载）

## 功能特性

✅ 支持下载 YouTube 视频
✅ 智能视频质量选择（优先级：720p > 480p > 360p > 1080p > 4K）
✅ 使用 cookies.txt 支持需要登录的视频
✅ RESTful API 接口
✅ 简洁的 Web 前端界面
✅ 解决中国访问问题（通过 Cloudflare CDN）

## 项目结构

```
yt-dlp-cloudflare/
├── backend/              # Koyeb 后端
│   ├── app.py           # Flask 应用
│   ├── requirements.txt # Python 依赖
│   ├── Dockerfile       # Docker 配置
│   └── .dockerignore
├── worker/              # Cloudflare Workers
│   ├── worker.js        # Workers 脚本
│   └── wrangler.toml    # Workers 配置
├── frontend/            # 前端页面
│   └── index.html       # Web 界面
├── cookies.txt          # YouTube cookies（可选）
└── README.md            # 本文档
```

## 部署步骤

### 第一步：部署 Koyeb 后端

#### 1. 注册 Koyeb 账号

访问 [Koyeb](https://www.koyeb.com/) 并注册免费账号（无需信用卡）。

#### 2. 准备 cookies.txt（可选但推荐）

如果需要下载需要登录的视频，请准备 cookies.txt 文件：

1. 安装浏览器扩展 [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
2. 登录 YouTube
3. 点击扩展图标，导出 cookies.txt
4. 将文件放在项目根目录

#### 3. 将 cookies.txt 复制到 backend 目录

```bash
cp cookies.txt backend/
```

#### 4. 配置 Cookies 路径（可选）

应用支持通过环境变量配置 cookies.txt 路径。默认路径为 `/app/cookies.txt`。

**方法 1：使用环境变量（推荐）**

在 Koyeb 部署时设置环境变量：
- 变量名：`COOKIES_PATH`
- 默认值：`/app/cookies.txt`

**方法 2：本地开发时使用命令行参数**

```bash
python app.py --cookies /path/to/your/cookies.txt --port 8000
```

#### 4. 配置代理（可选）

如果需要通过代理访问 YouTube（例如本地测试或网络受限环境），可以配置代理服务器。

**方法 1：使用环境变量**

在 Koyeb 部署时设置环境变量：
- 变量名：`PROXY_URL`
- 示例值：`socks5://127.0.0.1:1080` 或 `http://proxy.example.com:8080`

**方法 2：本地开发时使用命令行参数**

```bash
# 使用 SOCKS5 代理
python app.py --proxy socks5://127.0.0.1:50170

# 使用 HTTP 代理
python app.py --proxy http://proxy.example.com:8080

# 同时指定 cookies、代理和端口
python app.py --cookies ./cookies.txt --proxy socks5://127.0.0.1:50170 --port 8000
```

**支持的代理协议**：
- `http://` - HTTP 代理
- `https://` - HTTPS 代理
- `socks4://` - SOCKS4 代理
- `socks5://` - SOCKS5 代理（推荐）

#### 5. 部署到 Koyeb

**方法 A：通过 GitHub（推荐）**

1. 将代码推送到 GitHub 仓库
2. 登录 Koyeb Dashboard
3. 点击 "Create App"
4. 选择 "GitHub" 作为部署源
5. 选择你的仓库和分支
6. 配置部署：
   - **Builder**: Docker
   - **Dockerfile path**: `backend/Dockerfile`
   - **Port**: 8000
   - **Region**: Tokyo（距离中国最近）或 Singapore
   - **Instance type**: Free（512MB RAM）
   - **环境变量**（可选）：
     - `COOKIES_PATH`: 自定义 cookies 文件路径（默认：/app/cookies.txt）
     - `PROXY_URL`: 代理服务器地址（例如：socks5://127.0.0.1:1080）
7. 点击 "Deploy"

**方法 B：使用 Koyeb CLI**

```bash
# 安装 Koyeb CLI
curl -fsSL https://cli.koyeb.com/install.sh | sh

# 登录
koyeb login

# 进入 backend 目录
cd backend

# 部署应用
koyeb app init youtube-downloader --docker ./Dockerfile --ports 8000:http --routes /:8000
```

#### 6. 获取 Koyeb 应用 URL

部署完成后，Koyeb 会提供一个 URL，类似：
```
https://youtube-downloader-xxx.koyeb.app
```

**记录这个 URL，后面会用到！**

### 第二步：部署 Cloudflare Workers

#### 1. 安装 Wrangler CLI

```bash
npm install -g wrangler
```

#### 2. 登录 Cloudflare

```bash
wrangler login
```

这会打开浏览器，授权 Wrangler 访问你的 Cloudflare 账号。

#### 3. 配置 Worker

编辑 `worker/worker.js`，将第 9 行的 `YOUR_KOYEB_APP_URL` 替换为你的 Koyeb URL：

```javascript
// 修改前
const BACKEND_URL = 'YOUR_KOYEB_APP_URL';

// 修改后
const BACKEND_URL = 'https://youtube-downloader-xxx.koyeb.app';
```

#### 4. 部署 Worker

```bash
cd worker
wrangler deploy
```

部署成功后，会得到一个 Workers URL，类似：
```
https://youtube-downloader-proxy.your-username.workers.dev
```

**记录这个 URL！**

#### 5. 测试 Worker

```bash
curl https://youtube-downloader-proxy.your-username.workers.dev/health
```

应该返回：
```json
{"status":"ok","message":"Cloudflare Workers Proxy is running","backend":"..."}
```

### 第三步：部署前端页面（Cloudflare Pages）

#### 1. 配置前端

编辑 `frontend/index.html`，将第 137 行的 `YOUR_WORKER_URL` 替换为你的 Worker URL：

```javascript
// 修改前
const API_URL = 'YOUR_WORKER_URL';

// 修改后
const API_URL = 'https://youtube-downloader-proxy.your-username.workers.dev';
```

#### 2. 部署到 Cloudflare Pages

**方法 A：通过 GitHub（推荐）**

1. 将代码推送到 GitHub
2. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)
3. 进入 "Pages"
4. 点击 "Create a project"
5. 选择 "Connect to Git"
6. 选择你的仓库
7. 配置构建设置：
   - **Build command**: 留空
   - **Build output directory**: `frontend`
8. 点击 "Save and Deploy"

**方法 B：使用 Wrangler**

```bash
cd frontend
wrangler pages deploy . --project-name youtube-downloader
```

#### 3. 访问前端

部署完成后，你会得到一个 Pages URL，类似：
```
https://youtube-downloader.pages.dev
```

现在你可以在浏览器中打开这个 URL，开始下载视频了！

## API 文档

### 1. 获取视频信息

**端点**: `POST /api/info`

**请求体**:
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

**响应**:
```json
{
  "title": "视频标题",
  "duration": 213,
  "thumbnail": "https://...",
  "uploader": "上传者",
  "view_count": 1000000,
  "description": "视频描述..."
}
```

### 2. 下载视频

**端点**: `POST /api/download`

**请求体**:
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

**响应**: 视频文件流（video/mp4）

### 3. 健康检查

**端点**: `GET /health`

**响应**:
```json
{
  "status": "healthy"
}
```

## 视频质量优先级

系统会按照以下优先级自动选择视频质量：

1. **720p**（首选，平衡质量和文件大小）
2. **480p**（次选）
3. **360p**（再次）
4. **1080p**（较大文件）
5. **4K/2160p**（最大文件）

## 免费额度说明

### Koyeb 免费套餐
- ✅ 512MB RAM
- ✅ 100GB 月流量
- ✅ 永久免费
- ✅ 不休眠

### Cloudflare Workers 免费套餐
- ✅ 每天 100,000 请求
- ✅ 无限流量
- ✅ 永久免费

### Cloudflare Pages 免费套餐
- ✅ 无限请求
- ✅ 无限流量
- ✅ 永久免费

**结论**：完全可以免费使用，100GB/月流量对个人使用足够！

## 本地开发

### 后端开发

```bash
cd backend

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 运行开发服务器（默认配置）
python app.py

# 或者指定 cookies 路径和端口
python app.py --cookies /path/to/cookies.txt --port 8000

# 使用代理（本地测试推荐）
python app.py --proxy socks5://127.0.0.1:50170

# 完整配置示例
python app.py --cookies ./cookies.txt --proxy socks5://127.0.0.1:50170 --port 8000

# 查看所有参数
python app.py --help
```

访问 `http://localhost:8000`

**命令行参数说明**：
- `--cookies`: cookies.txt 文件路径（默认：/app/cookies.txt）
- `--port`: 服务器端口（默认：从环境变量 PORT 读取，或 8000）
- `--proxy`: 代理服务器地址（例如：socks5://127.0.0.1:50170）

### Worker 本地测试

```bash
cd worker
wrangler dev
```

访问 `http://localhost:8787`

## 配置说明

### Cookies 文件路径配置

应用支持多种方式配置 cookies.txt 文件路径：

#### 1. 环境变量（推荐用于生产环境）

设置 `COOKIES_PATH` 环境变量：

```bash
# Docker 运行时
docker run -e COOKIES_PATH=/app/my-cookies.txt your-image

# Koyeb 部署
# 在 Koyeb Dashboard 的环境变量中设置：
# COOKIES_PATH = /app/cookies.txt
```

#### 2. 命令行参数（推荐用于本地开发）

```bash
# 指定 cookies 路径
python app.py --cookies /path/to/cookies.txt

# 同时指定端口
python app.py --cookies /path/to/cookies.txt --port 8000
```

#### 3. 默认路径

如果未配置，默认使用 `/app/cookies.txt`。

### Docker 部署示例

**使用默认路径**：
```bash
docker build -t youtube-downloader ./backend
docker run -p 8000:8000 youtube-downloader
```

**使用自定义 cookies 路径**：
```bash
# 挂载外部 cookies 文件
docker run -p 8000:8000 \
  -v /path/to/your/cookies.txt:/app/my-cookies.txt \
  -e COOKIES_PATH=/app/my-cookies.txt \
  youtube-downloader
```

### 代理配置

应用支持多种方式配置代理服务器：

#### 1. 环境变量（推荐用于生产环境）

设置 `PROXY_URL` 环境变量：

```bash
# Docker 运行时
docker run -e PROXY_URL=socks5://127.0.0.1:1080 your-image

# Koyeb 部署
# 在 Koyeb Dashboard 的环境变量中设置：
# PROXY_URL = socks5://proxy.example.com:1080
```

#### 2. 命令行参数（推荐用于本地开发）

```bash
# 指定代理
python app.py --proxy socks5://127.0.0.1:50170

# 同时指定 cookies 和代理
python app.py --cookies ./cookies.txt --proxy socks5://127.0.0.1:50170
```

#### 3. 支持的代理协议

- **HTTP**: `http://proxy.example.com:8080`
- **HTTPS**: `https://proxy.example.com:8080`
- **SOCKS4**: `socks4://127.0.0.1:1080`
- **SOCKS5**: `socks5://127.0.0.1:1080`（推荐，支持 UDP 和认证）

#### 4. 代理认证

如果代理需要认证，可以在 URL 中包含用户名和密码：

```bash
# HTTP 代理认证
python app.py --proxy http://username:password@proxy.example.com:8080

# SOCKS5 代理认证
python app.py --proxy socks5://username:password@127.0.0.1:1080
```

#### 5. Docker 部署示例（使用代理）

```bash
# 同时配置 cookies 和代理
docker run -p 8000:8000 \
  -v /path/to/cookies.txt:/app/cookies.txt \
  -e COOKIES_PATH=/app/cookies.txt \
  -e PROXY_URL=socks5://127.0.0.1:1080 \
  youtube-downloader
```

## 故障排查

### 问题 1：Koyeb 部署失败

**解决方案**：
- 检查 Dockerfile 路径是否正确
- 确保 cookies.txt 存在（或修改 Dockerfile 使其可选）
- 查看 Koyeb 日志

### 问题 2：Worker 返回 502 错误

**解决方案**：
- 检查 `BACKEND_URL` 是否配置正确
- 确保 Koyeb 应用正在运行
- 测试 Koyeb URL 是否可直接访问

### 问题 3：下载视频失败

**解决方案**：
- 检查 YouTube URL 是否正确
- 确保视频没有地区限制
- 如果视频需要登录，确保 cookies.txt 正确配置
- 查看 Koyeb 应用日志

### 问题 4：SSL 证书验证失败（使用代理时）

**错误信息**：
```
[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate
```

**原因**：
某些代理服务器（特别是 SOCKS5 代理）会对 HTTPS 流量进行中间人检查，导致 SSL 证书验证失败。

**解决方案**：
✅ 已自动修复！应用已禁用 SSL 证书验证（`nocheckcertificate: True`），无需手动配置。

**如果仍有问题**：
1. 确认代理服务器正常运行
2. 尝试更换代理协议（如从 SOCKS5 切换到 HTTP）
3. 检查代理服务器的证书设置

**安全说明**：
禁用证书验证会降低安全性，但对于访问 YouTube 这样的公开网站是安全的。如果您对此有顾虑，可以：
- 使用不进行 HTTPS 中间人检查的代理
- 在不使用代理的环境中运行

### 问题 5：中国无法访问

**解决方案**：
- 确保使用的是 Cloudflare Workers URL，不是直接访问 Koyeb
- 检查 Cloudflare Workers 是否部署成功
- 尝试更换 Cloudflare 域名或使用自定义域名

## 技术栈

- **后端**: Python 3.11 + Flask + yt-dlp
- **代理层**: Cloudflare Workers (JavaScript)
- **前端**: HTML + CSS + JavaScript (原生)
- **部署**: Koyeb (Docker) + Cloudflare (Pages + Workers)

## 许可证

MIT License

## 免责声明

本项目仅供学习和个人使用。请遵守 YouTube 服务条款，尊重版权。下载的视频内容不得用于商业用途。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 作者

基于用户需求开发，由 Claude Code 实现。
