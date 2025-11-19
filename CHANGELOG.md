# 更新日志

## 2024-11-20 v1.1.3 - Bot 检测优化 & 中文显示完善

### 改进

1. **YouTube Bot 检测优化**
   - 添加 `user_agent` 选项，模拟真实浏览器
   - 添加 `extractor_args` 配置，使用多个客户端（android、web）
   - 优化参数以减少被 YouTube 识别为 bot 的概率

2. **中文显示完全修复**
   - 修复所有 JSON 响应（包括错误信息）的中文显示
   - 所有 API 端点统一使用 `json.dumps(ensure_ascii=False)`
   - 统一设置响应头 `Content-Type: application/json; charset=utf-8`
   - 错误信息也能正确显示中文

### 效果对比

**修复前（错误信息）**：
```json
{"error": "\u83b7\u53d6\u4fe1\u606f\u5931\u8d25: ..."}
```

**修复后（错误信息）**：
```json
{"error": "获取信息失败: ..."}
```

---

## 2024-11-20 v1.1.2 - 中文显示优化

### 改进

1. **JSON 响应中文显示**
   - 在 `/api/info` 端点使用 `json.dumps(result, ensure_ascii=False)`
   - 显式设置响应头 `Content-Type: application/json; charset=utf-8`
   - 中文字符直接显示，不再显示为 Unicode 编码（如 `\u4e2d\u56fd`）
   - 配置 `JSON_AS_ASCII = False` 作为全局配置（兜底）

### 效果对比

**修复前**：
```json
{
  "title": "\u4e2d\u56fd\u526f\u603b\u7406\u5218\u9e64...",
  "uploader": "\u7f8e\u56fd\u4e4b\u97f3\u4e2d\u6587\u7f51"
}
```

**修复后**：
```json
{
  "title": "中国副总理刘鹤...",
  "uploader": "美国之音中文网"
}
```

---

## 2024-11-20 v1.1.1 - SSL 证书验证修复

### 修复

1. **SSL 证书验证问题**
   - 禁用 SSL 证书验证（`nocheckcertificate: True`）
   - 解决使用代理时的证书验证失败问题
   - 修复错误：`[SSL: CERTIFICATE_VERIFY_FAILED]`

### 说明

在使用代理（特别是 SOCKS5 代理）时，某些代理服务器会对 HTTPS 流量进行中间人检查，导致 SSL 证书验证失败。通过禁用证书验证，可以避免这个问题。

**注意**：这个设置会降低安全性，但对于访问 YouTube 这样的公开网站是安全的。

---

## 2024-11-20 v1.1.0 - 代理支持

### 新增功能

1. **代理服务器支持**
   - 支持通过代理访问 YouTube
   - 可通过环境变量 `PROXY_URL` 配置代理
   - 可通过命令行参数 `--proxy` 指定代理
   - 支持多种代理协议：HTTP、HTTPS、SOCKS4、SOCKS5
   - 支持代理认证（用户名/密码）

2. **命令行参数增强**
   - 新增 `--proxy` 参数，用于指定代理服务器地址

### 修改的文件

1. **backend/app.py**
   - 添加全局变量 `PROXY_URL` 存储代理配置
   - 在 `download_video()` 和 `get_video_info()` 函数中添加代理支持
   - 在 `parse_args()` 函数中添加 `--proxy` 参数
   - 在主函数中添加代理配置处理

2. **backend/entrypoint.sh**
   - 添加 `PROXY_URL` 环境变量支持
   - 启动时输出代理配置信息

3. **README.md**
   - 添加代理配置说明章节
   - 更新命令行参数说明
   - 添加 Docker 和 Koyeb 部署的代理配置示例
   - 添加代理认证说明

### 使用方法

#### 本地开发

```bash
# 使用 SOCKS5 代理
python app.py --proxy socks5://127.0.0.1:50170

# 使用 HTTP 代理
python app.py --proxy http://proxy.example.com:8080

# 完整配置
python app.py --cookies ./cookies.txt --proxy socks5://127.0.0.1:50170 --port 8000
```

#### Docker 部署

```bash
docker run -p 8000:8000 \
  -e PROXY_URL=socks5://127.0.0.1:1080 \
  your-image
```

#### Koyeb 部署

在环境变量中设置：
- `PROXY_URL=socks5://your-proxy.com:1080`

### 支持的代理协议

- HTTP: `http://proxy.example.com:8080`
- HTTPS: `https://proxy.example.com:8080`
- SOCKS4: `socks4://127.0.0.1:1080`
- SOCKS5: `socks5://127.0.0.1:1080`（推荐）

### 向后兼容性

✅ 完全向后兼容。代理配置是可选的，不设置时将直接连接。

---

## 2024-11-20 v1.0.0 - Cookies 路径配置增强

### 新增功能

1. **支持自定义 Cookies 路径**
   - 可通过环境变量 `COOKIES_PATH` 配置 cookies.txt 路径
   - 可通过命令行参数 `--cookies` 指定 cookies 路径
   - 默认路径：`/app/cookies.txt`

2. **命令行参数支持**
   - `--cookies`: 指定 cookies.txt 文件路径
   - `--port`: 指定服务器端口
   - `--help`: 查看帮助信息

3. **Docker 启动脚本**
   - 新增 `entrypoint.sh` 启动脚本
   - 支持通过环境变量配置 cookies 路径
   - 自动检查 cookies 文件是否存在

### 修改的文件

1. **backend/app.py**
   - 添加 `argparse` 支持命令行参数
   - 支持从环境变量 `COOKIES_FILE` 读取 cookies 路径
   - 启动时自动检查 cookies 文件状态
   - 移除硬编码的 cookies 路径检查逻辑

2. **backend/Dockerfile**
   - 添加 `entrypoint.sh` 脚本
   - 使用 `ENTRYPOINT` 代替 `CMD`
   - 添加 `COOKIES_PATH` 环境变量（默认值：/app/cookies.txt）

3. **backend/entrypoint.sh**（新增）
   - Bash 启动脚本
   - 从环境变量读取 `COOKIES_PATH`
   - 设置 `COOKIES_FILE` 环境变量供 Flask 应用使用
   - 启动 gunicorn 服务器

4. **README.md**
   - 添加 Cookies 路径配置说明
   - 添加环境变量配置示例
   - 添加命令行参数使用说明
   - 添加 Docker 部署示例

### 使用方法

#### 本地开发

```bash
# 使用默认配置
python app.py

# 指定 cookies 路径
python app.py --cookies /path/to/cookies.txt

# 指定端口和 cookies
python app.py --cookies /path/to/cookies.txt --port 8000
```

#### Docker 部署

```bash
# 使用默认 cookies 路径
docker run -p 8000:8000 your-image

# 使用自定义 cookies 路径
docker run -p 8000:8000 \
  -v /path/to/cookies.txt:/app/my-cookies.txt \
  -e COOKIES_PATH=/app/my-cookies.txt \
  your-image
```

#### Koyeb 部署

在 Koyeb Dashboard 中设置环境变量：
- 变量名：`COOKIES_PATH`
- 变量值：`/app/cookies.txt`（或自定义路径）

### 向后兼容性

✅ 完全向后兼容。如果不设置任何参数，应用将使用默认路径 `/app/cookies.txt`。

### 优先级

配置优先级（从高到低）：
1. 命令行参数 `--cookies`（仅在直接运行 Python 时）
2. 环境变量 `COOKIES_FILE`（Flask 应用读取）
3. 环境变量 `COOKIES_PATH`（entrypoint.sh 读取并设置 COOKIES_FILE）
4. 默认值：`/app/cookies.txt`
