#!/usr/bin/env bash
# 🌴 森林小岛日报 · Mira 数据接收脚本
# 用法：./mira-update.sh <today.json 的 URL>
# 作用：下载 Mira 生成的 today.json → 合并 → 推送

set -e
cd "$(dirname "$0")"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${CYAN}▶${NC} $1"; }
ok()   { echo -e "${GREEN}✓${NC} $1"; }
err()  { echo -e "${RED}✗${NC} $1"; exit 1; }

URL="$1"
[ -z "$URL" ] && err "用法: ./mira-update.sh <today.json URL>"
[ -d .git ] || err "当前目录不是 git 仓库"

log "下载 Mira 数据..."
curl -sSL "$URL" -o data/today.json || err "下载失败"

# 校验 JSON
python3 -c "import json; json.load(open('data/today.json'))" || err "JSON 格式错误"
COUNT=$(python3 -c "import json; print(len(json.load(open('data/today.json'))))")
ok "下载成功：$COUNT 条新内容"

log "合并去重..."
python3 scripts/generate.py

git add data/
if git diff --cached --quiet; then
    echo "⚠️  没有新内容（可能已经合并过了）"
    exit 0
fi

TODAY=$(date +%Y-%m-%d)
git commit -m "📰 mira update: $TODAY"
log "推送中..."
git push

REMOTE=$(git remote get-url origin 2>/dev/null)
ok "完成！网页将在 1~2 分钟后更新"
echo "  🌐 ${REMOTE%.git}/actions"
