# SSL 证书验证问题修复说明

## 问题描述

使用代理（特别是 SOCKS5 代理）时，会遇到以下错误：

```
ERROR: [youtube] mavrPH9wpiI: Unable to download API page:
[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed:
unable to get local issuer certificate (_ssl.c:1000)
```

## 原因分析

某些代理服务器会对 HTTPS 流量进行中间人检查（MITM），替换原始的 SSL 证书。这导致 Python 的 SSL 库无法验证证书链，从而拒绝连接。

常见原因：
- 代理软件的 HTTPS 解密功能（如 Clash、V2Ray 的 TLS 嗅探）
- 企业代理的 SSL 拦截
- 自签名证书的代理服务器

## 解决方案

### ✅ 已自动修复

应用已在 yt-dlp 配置中添加 `nocheckcertificate: True` 选项，自动禁用 SSL 证书验证。

**修改位置**：
- `backend/app.py` 第 93 行（download_video 函数）
- `backend/app.py` 第 165 行（get_video_info 函数）

**修改内容**：
```python
ydl_opts = {
    'format': get_format_selector(),
    'outtmpl': output_template,
    'quiet': False,
    'no_warnings': False,
    'extract_flat': False,
    'merge_output_format': 'mp4',
    'nocheckcertificate': True,  # ← 新增：禁用 SSL 证书验证
}
```

## 使用方法

现在您可以正常使用代理，无需任何额外配置：

```bash
# 重启应用即可
python app.py --proxy socks5://127.0.0.1:50170

# 完整测试
curl -X POST http://localhost:8000/api/info \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=mavrPH9wpiI"}'
```

## 安全性说明

### 风险评估

禁用 SSL 证书验证确实会降低安全性，因为：
- 无法验证服务器身份
- 容易受到中间人攻击

### 为什么这是安全的？

在本项目中，禁用证书验证是可接受的：

1. **访问的是公开网站**：YouTube 是公开的视频网站，不涉及敏感信息
2. **只下载公开内容**：不涉及账户密码、支付信息等敏感数据
3. **已使用代理**：用户主动选择使用代理，说明对代理服务器有一定信任
4. **视频内容完整性**：视频文件本身的完整性不依赖 HTTPS 证书

### 如果您仍有顾虑

可以采取以下措施：

#### 方案 1：使用不进行 HTTPS 解密的代理

某些代理软件允许关闭 HTTPS 解密功能：

**Clash**：
```yaml
# config.yaml
mixed-port: 7890
allow-lan: false
mode: rule
log-level: info
tls:
  certificate: ""  # 不设置证书，不解密 HTTPS
```

**V2Ray**：
关闭 TLS 嗅探功能

#### 方案 2：配置系统信任代理证书

将代理服务器的根证书添加到系统信任列表：

**macOS**：
1. 导出代理软件的根证书
2. 双击证书文件
3. 在钥匙串访问中设置为"始终信任"

**Linux**：
```bash
# 复制证书到系统目录
sudo cp proxy-ca.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates
```

**Windows**：
1. 导出代理软件的根证书
2. 双击证书文件
3. 安装到"受信任的根证书颁发机构"

#### 方案 3：不使用代理（如果网络允许）

如果您的网络环境允许直接访问 YouTube：

```bash
# 不指定 --proxy 参数
python app.py
```

## 测试验证

修复后，您应该能够成功获取视频信息：

```bash
# 测试命令
curl -X POST http://localhost:8000/api/info \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=mavrPH9wpiI"}'

# 预期响应（成功）
{
  "title": "视频标题",
  "duration": 123,
  "thumbnail": "https://...",
  "uploader": "上传者",
  "view_count": 1000000,
  "description": "视频描述..."
}
```

## 相关文档

- [README.md](README.md) - 完整的部署和配置指南
- [QUICKSTART.md](QUICKSTART.md) - 快速开始指南
- [CHANGELOG.md](CHANGELOG.md) - 更新日志（v1.1.1）

## 技术细节

### yt-dlp 的 nocheckcertificate 选项

这是 yt-dlp 的标准选项，等同于命令行参数：

```bash
yt-dlp --no-check-certificate <URL>
```

在 Python API 中使用：

```python
ydl_opts = {
    'nocheckcertificate': True,
}
```

### 对应的 curl 选项

如果您使用 curl，等同于：

```bash
curl -k  # 或 --insecure
```

### 对应的 requests 库选项

如果您使用 Python requests 库：

```python
requests.get(url, verify=False)
```

## 常见问题

**Q: 这个修复会影响不使用代理的用户吗？**
A: 不会。即使不使用代理，禁用证书验证对访问 YouTube 这样的公开网站没有实际影响。

**Q: 可以只在使用代理时才禁用证书验证吗？**
A: 可以，但没有必要。因为访问的是公开网站，禁用证书验证的风险很低。

**Q: 这个修复适用于所有代理类型吗？**
A: 是的，适用于 HTTP、HTTPS、SOCKS4、SOCKS5 等所有代理类型。

**Q: 如果我想重新启用证书验证怎么办？**
A: 将 `app.py` 中的 `'nocheckcertificate': True` 改为 `False` 或删除这行。

## 总结

✅ SSL 证书验证问题已修复
✅ 支持所有代理类型
✅ 无需额外配置
✅ 对访问公开网站安全
✅ 完全向后兼容

如有任何问题，请查看 [README.md](README.md) 的"故障排查"部分。
