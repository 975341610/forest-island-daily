#!/usr/bin/env bash
# 🌴 森林小岛日报 · 一键推送脚本（macOS / Linux 双击运行）
# 工作流：
#   1. 你从飞书把 today.json 保存到 forest-island-daily/data/today.json
#   2. 双击本文件（macOS Finder / Linux 文件管理器）
#   3. 脚本自动合并 + commit + push

# 切到脚本所在目录
cd "$(dirname "$0")" || exit 1

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'

echo ""
echo "🌴 ========================================"
echo "   森林小岛日报 · 自动推送"
echo "========================================"
echo ""

# 检查 today.json 是否存在
if [ ! -f "data/today.json" ]; then
    echo -e "${RED}✗${NC} 没找到 data/today.json"
    echo ""
    echo "请先："
    echo "  1. 打开飞书私聊，找到 Mira 发送的 today.json 附件"
    echo "  2. 右键 → 另存为 → 保存到 $(pwd)/data/today.json"
    echo "  3. 重新双击本脚本"
    echo ""
    read -n 1 -s -r -p "按任意键关闭..."
    exit 1
fi

# 校验 JSON 格式
if ! python3 -c "import json; json.load(open('data/today.json'))" 2>/dev/null; then
    echo -e "${RED}✗${NC} today.json 格式有误"
    read -n 1 -s -r -p "按任意键关闭..."
    exit 1
fi

COUNT=$(python3 -c "import json; print(len(json.load(open('data/today.json'))))")
echo -e "${GREEN}✓${NC} 检测到 today.json (共 $COUNT 条)"
echo ""

# 检查是不是 git 仓库
if [ ! -d ".git" ]; then
    echo -e "${RED}✗${NC} 当前目录不是 git 仓库"
    echo "请先 cd 到 forest-island-daily 目录，运行："
    echo "  git init && git remote add origin <你的仓库URL>"
    read -n 1 -s -r -p "按任意键关闭..."
    exit 1
fi

# 合并 + 去重
echo -e "${CYAN}▶${NC} 合并到 archive..."
python3 scripts/generate.py
echo ""

# git 操作
git add data/
if git diff --cached --quiet; then
    echo -e "${YELLOW}⚠${NC} 没有新内容（可能今天的数据已经合并过）"
    read -n 1 -s -r -p "按任意键关闭..."
    exit 0
fi

TODAY=$(date +%Y-%m-%d)
echo -e "${CYAN}▶${NC} 提交 + 推送..."
git commit -m "📰 mira daily: $TODAY"

if git push 2>&1; then
    echo ""
    echo -e "${GREEN}✅ 推送完成！${NC}"
    REMOTE=$(git remote get-url origin 2>/dev/null)
    echo "  🌐 网页将在 1-2 分钟后更新"
    echo "  📊 ${REMOTE%.git}/actions"
else
    echo ""
    echo -e "${RED}✗${NC} push 失败，请检查网络/权限"
fi

echo ""
read -n 1 -s -r -p "按任意键关闭..."
