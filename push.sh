#!/usr/bin/env bash
# 🌴 森林小岛日报 · 本地一键更新脚本
# 用法：./push.sh           # 抓取 + 合并 + 推送
#      ./push.sh --no-fetch # 跳过抓取，只推送本地改动
#      ./push.sh --dry      # 试运行，不真的 push

set -e
cd "$(dirname "$0")"

# ===== 配色 =====
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${CYAN}▶${NC} $1"; }
ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
err()  { echo -e "${RED}✗${NC} $1"; exit 1; }

# ===== 解析参数 =====
NO_FETCH=0; DRY=0
for arg in "$@"; do
    case "$arg" in
        --no-fetch) NO_FETCH=1 ;;
        --dry)      DRY=1 ;;
        -h|--help)
            echo "用法: ./push.sh [--no-fetch] [--dry]"
            exit 0 ;;
    esac
done

# ===== 前置检查 =====
[ -d .git ] || err "当前目录不是 git 仓库，请先 git init && git remote add origin <url>"
command -v python3 >/dev/null || err "未找到 python3"
command -v git >/dev/null || err "未找到 git"

# ===== 1. 抓取今日数据 =====
if [ $NO_FETCH -eq 0 ]; then
    log "抓取今日新闻..."
    python3 scripts/fetch_news.py || err "fetch_news.py 失败"
    ok "today.json 已生成"
else
    warn "跳过抓取（--no-fetch）"
fi

# ===== 2. 合并到 archive =====
log "合并去重..."
python3 scripts/generate.py || err "generate.py 失败"

# ===== 3. 检查是否有变更 =====
git add data/
if git diff --cached --quiet; then
    warn "没有新内容需要推送，退出"
    exit 0
fi

# ===== 4. 预览变更 =====
echo ""
log "本次变更："
git diff --cached --stat
echo ""

# ===== 5. 试运行 =====
if [ $DRY -eq 1 ]; then
    warn "DRY RUN — 不会真的 commit/push"
    git reset HEAD data/ >/dev/null
    exit 0
fi

# ===== 6. 提交并推送 =====
TODAY=$(date +%Y-%m-%d)
COMMIT_MSG="📰 manual update: $TODAY"
log "提交：$COMMIT_MSG"
git commit -m "$COMMIT_MSG" || err "commit 失败"

log "推送到远端..."
git push || err "push 失败（请检查网络/权限）"

# ===== 7. 提示 =====
REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
ok "推送完成！"
echo ""
echo "  📦 仓库：$REMOTE_URL"
echo "  🌐 网页将在 1~2 分钟后自动更新"
echo "  📊 查看部署进度：${REMOTE_URL%.git}/actions"
echo ""
