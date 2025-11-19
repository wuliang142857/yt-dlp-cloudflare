# YouTube Bot 检测问题解决方案

## 问题描述

在 Koyeb 等服务器环境部署后，访问 YouTube 视频时可能遇到以下错误：

```
ERROR: [youtube] Sign in to confirm you're not a bot.
Use --cookies-from-browser or --cookies for the authentication.
```

本地测试正常，但部署到服务器后出现此问题。

## 原因分析

YouTube 使用多种机制检测机器人访问：

1. **IP 地址识别**：
   - 云服务器（如 Koyeb、AWS）的 IP 地址被标记为可疑
   - 来自数据中心的请求更容易被识别为 bot

2. **请求特征**：
   - 缺少浏览器特征（User-Agent、Headers 等）
   - 请求模式异常（频率、时间等）

3. **Cookies 问题**：
   - Cookies 已过期
   - Cookies 与请求来源不匹配
   - 未提供有效的 cookies

## 已实施的解决方案

应用已内置以下优化（v1.1.3+）：

### 1. User-Agent 模拟

```python
'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
```

模拟真实的 Chrome 浏览器。

### 2. 多客户端策略

```python
'extractor_args': {
    'youtube': {
        'player_client': ['android', 'web'],
        'skip': ['dash', 'hls'],
    }
}
```

使用 Android 和 Web 客户端，增加成功率。

### 3. SSL 证书验证禁用

```python
'nocheckcertificate': True
```

避免代理环境的证书问题。

## 额外解决方案

如果仍然遇到 bot 检测，可以尝试以下方法：

### 方案 1：更新 Cookies（推荐）

Cookies 可能已过期，需要重新导出。

#### 步骤：

1. **安装浏览器扩展**：
   - Chrome/Edge: [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
   - Firefox: [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)

2. **导出新的 Cookies**：
   ```bash
   # 1. 在浏览器中登录 YouTube
   # 2. 访问任意 YouTube 视频页面
   # 3. 点击扩展图标
   # 4. 下载 cookies.txt
   ```

3. **替换 Cookies 文件**：
   ```bash
   # 本地测试
   cp ~/Downloads/cookies.txt backend/cookies.txt

   # 重新部署到 Koyeb
   git add backend/cookies.txt
   git commit -m "Update cookies"
   git push
   ```

4. **验证 Cookies**：
   ```bash
   # 检查 cookies 文件格式
   head -n 5 backend/cookies.txt

   # 应该看到类似这样的内容：
   # # Netscape HTTP Cookie File
   # .youtube.com	TRUE	/	TRUE	...
   ```

### 方案 2：使用代理（生产环境）

如果您的 Koyeb 服务需要长期稳定运行，建议配置代理：

```bash
# 在 Koyeb 环境变量中设置
PROXY_URL=socks5://your-proxy.com:1080
```

**推荐的代理类型**：
- 住宅代理（Residential Proxy）- 最佳效果
- 数据中心代理（Datacenter Proxy）- 中等效果
- 免费代理 - 不推荐（成功率低）

### 方案 3：切换 Koyeb Region

不同地区的 IP 封禁程度不同：

1. 登录 Koyeb Dashboard
2. 进入应用设置
3. 切换到不同的 Region：
   - Tokyo（东京）
   - Singapore（新加坡）
   - Frankfurt（法兰克福）
4. 重新部署

### 方案 4：使用 OAuth 认证（高级）

如果您有 Google OAuth 凭据，可以使用 OAuth 认证代替 cookies：

```python
# 在 ydl_opts 中添加
'username': 'oauth',
'password': ''  # OAuth 会自动处理
```

**注意**：此方法需要额外配置，不推荐初学者使用。

## 检查清单

部署到 Koyeb 后遇到 bot 检测，请按以下顺序排查：

- [ ] **Cookies 文件存在**：
  ```bash
  # 查看 Koyeb 日志，应该看到：
  # INFO:app:已配置 cookies 文件: /app/cookies.txt
  ```

- [ ] **Cookies 文件有效**：
  - 确认是最近（7天内）导出的
  - 确认导出时已登录 YouTube
  - 确认文件格式正确（Netscape 格式）

- [ ] **yt-dlp 版本最新**：
  ```bash
  # 检查 requirements.txt
  yt-dlp==2025.11.12  # 或更新版本
  ```

- [ ] **应用配置正确**：
  - User-Agent 已设置
  - extractor_args 已配置
  - nocheckcertificate 已启用

- [ ] **尝试不同的视频**：
  - 某些视频可能有额外限制
  - 尝试公开的、无地区限制的视频

## 测试命令

### 本地测试

```bash
# 使用本地 cookies 测试
cd backend
python app.py --cookies ./cookies.txt

# 测试 API
curl -X POST http://localhost:8000/api/info \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

### Koyeb 测试

```bash
# 测试 Koyeb 部署
curl -X POST https://your-app.koyeb.app/api/info \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

## 常见问题

### Q: 本地可以，Koyeb 不行？

A: 这很正常。本地使用的是您的家庭 IP，Koyeb 使用的是数据中心 IP。解决方法：
1. 更新 cookies（确保是最新的）
2. 配置代理
3. 切换 Koyeb Region

### Q: Cookies 多久需要更新一次？

A: 建议每周更新一次。YouTube cookies 的有效期通常为 30-60 天，但为了保险，建议更频繁地更新。

### Q: 是否需要 YouTube Premium？

A: 不需要。普通 YouTube 账号即可。但 Premium 账号可能有更好的稳定性。

### Q: 能否完全避免 bot 检测？

A: 很难完全避免。建议的最佳实践：
1. 定期更新 cookies
2. 使用住宅代理
3. 控制请求频率
4. 监控错误日志

## 监控和维护

### 设置告警

建议设置监控，当出现 bot 检测时及时处理：

```bash
# 监控 Koyeb 日志中的关键词
# "Sign in to confirm you're not a bot"
# "ERROR: [youtube]"
```

### 定期维护

建议的维护计划：

| 任务 | 频率 | 说明 |
|------|------|------|
| 更新 cookies | 每周 | 确保 cookies 有效 |
| 检查日志 | 每天 | 监控错误情况 |
| 更新 yt-dlp | 每月 | 获取最新的反检测优化 |
| 测试下载 | 每周 | 验证服务正常 |

## 相关资源

- [yt-dlp Wiki - FAQ](https://github.com/yt-dlp/yt-dlp/wiki/FAQ)
- [yt-dlp Wiki - Extractors](https://github.com/yt-dlp/yt-dlp/wiki/Extractors)
- [如何导出 YouTube Cookies](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies)

## 总结

✅ **v1.1.3+ 已内置优化**，减少 bot 检测概率

🔑 **最重要的是 Cookies**：
- 确保 cookies.txt 文件存在
- 定期更新（每周）
- 导出时已登录 YouTube

🌐 **如果仍有问题**：
- 配置代理（住宅代理最佳）
- 切换 Koyeb Region
- 控制请求频率

如有任何问题，请查看 [README.md](README.md) 的"故障排查"部分。
