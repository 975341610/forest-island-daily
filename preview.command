#!/usr/bin/env bash
# 🌴 森林小岛日报 · 本地预览（解决 file:// fetch 限制）
# macOS / Linux：双击即可
cd "$(dirname "$0")" || exit 1

PORT=8000

echo ""
echo "🌴 ========================================"
echo "   森林小岛日报 · 本地预览服务器"
echo "========================================"
echo ""
echo "📡 启动地址：http://localhost:$PORT"
echo "⏹  关闭服务：按 Ctrl + C"
echo ""

# 自动打开浏览器（macOS）
if command -v open >/dev/null 2>&1; then
    (sleep 1 && open "http://localhost:$PORT") &
# Linux
elif command -v xdg-open >/dev/null 2>&1; then
    (sleep 1 && xdg-open "http://localhost:$PORT") &
fi

# 起服务
if command -v python3 >/dev/null 2>&1; then
    python3 -m http.server $PORT
elif command -v python >/dev/null 2>&1; then
    python -m http.server $PORT
else
    echo "❌ 未找到 python，请先安装 Python 3"
    read -n 1 -s -r -p "按任意键关闭..."
    exit 1
fi
