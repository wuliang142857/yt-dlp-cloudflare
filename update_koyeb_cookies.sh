#!/bin/bash
set -e

# 配置
PROJECT_DIR="/Users/admin/zone/yt-dlp-cloudflare"
KOYEB_APP_NAME="grateful-meghan"
KOYEB_SERVICE_NAME="yt-dlp-cloudflare"

echo "================================================================================"
echo "Koyeb Cookies 自动更新脚本"
echo "================================================================================"
echo ""

# 检查 Koyeb CLI 是否安装
if ! command -v koyeb &> /dev/null; then
    echo "❌ Koyeb CLI 未安装"
    echo ""
    echo "请先安装 Koyeb CLI:"
    echo "  # macOS"
    echo "  brew install koyeb/tap/koyeb-cli"
    echo ""
    echo "  # 或直接下载"
    echo "  curl -fsSL https://cli.koyeb.com/install.sh | sh"
    echo ""
    exit 1
fi

# 检查是否已登录
if ! koyeb service list --app "$KOYEB_APP_NAME" &> /dev/null; then
    echo "❌ 未登录 Koyeb 或应用不存在"
    echo ""
    echo "请先登录:"
    echo "  koyeb login"
    echo ""
    exit 1
fi

echo "🍪 导出本地 Firefox cookies..."
cd "$PROJECT_DIR"

if [ ! -f "export_cookies_firefox.py" ]; then
    echo "❌ 找不到 export_cookies_firefox.py"
    exit 1
fi

# 导出 cookies
if ! python3 export_cookies_firefox.py > /tmp/cookies_new.txt 2>/dev/null; then
    echo "❌ Cookies 导出失败"
    echo ""
    echo "请确保:"
    echo "  1. Firefox 浏览器已安装"
    echo "  2. 已使用 Firefox 访问并登录需要的网站（如 YouTube）"
    echo "  3. Firefox 已关闭（建议先运行: pkill firefox）"
    echo ""
    exit 1
fi

# 检查导出的 cookies 是否有效
COOKIE_COUNT=$(grep -v '^#' /tmp/cookies_new.txt | grep -v '^$' | wc -l | tr -d ' ')

if [ "$COOKIE_COUNT" -lt 5 ]; then
    echo "❌ Cookies 数量太少 ($COOKIE_COUNT 个)，可能导出失败"
    rm /tmp/cookies_new.txt
    exit 1
fi

echo "✅ 成功导出 $COOKIE_COUNT 个 cookies"
echo ""

echo "🔐 编码 cookies 为 base64..."
# macOS 的 base64 命令需要 -i 参数
if [[ "$OSTYPE" == "darwin"* ]]; then
    COOKIES_BASE64=$(base64 -i /tmp/cookies_new.txt | tr -d '\n')
else
    COOKIES_BASE64=$(base64 -w 0 /tmp/cookies_new.txt)
fi

echo "📊 编码后大小: ${#COOKIES_BASE64} 字符"
echo ""

echo "📤 更新 Koyeb 环境变量..."
echo "   应用: $KOYEB_APP_NAME"
echo "   服务: $KOYEB_SERVICE_NAME"
echo ""

# 更新服务
if koyeb services update "$KOYEB_SERVICE_NAME" \
    --app "$KOYEB_APP_NAME" \
    --env COOKIES_BASE64="$COOKIES_BASE64"; then

    echo ""
    echo "✅ Cookies 已成功更新到 Koyeb！"
    echo ""
    echo "🔄 Koyeb 将在几秒钟内自动重启服务以应用新配置"
    echo ""
    echo "💡 提示："
    echo "   - 可以在 Koyeb Dashboard 查看部署状态"
    echo "   - 访问 https://app.koyeb.com/apps/$KOYEB_APP_NAME"
    echo ""
else
    echo ""
    echo "❌ 更新失败！"
    echo ""
    echo "请检查："
    echo "  1. 应用名称和服务名称是否正确"
    echo "  2. 是否有权限更新该服务"
    echo "  3. 网络连接是否正常"
    echo ""
    rm /tmp/cookies_new.txt
    exit 1
fi

# 清理临时文件
rm /tmp/cookies_new.txt

echo "================================================================================"
echo "完成！"
echo "================================================================================"
