#!/usr/bin/env bash
# 森林小岛日报 · 首次部署一键脚本
# 用途：把本地工程包推送到 GitHub 并启用 Pages
# 用法：双击运行（macOS Finder / Linux 文件管理器）
#       或终端执行 ./deploy.command
#
# 设计原则：
#   - 不使用 && / || 链式语法，每步独立检查
#   - 推送失败绝不打开浏览器
#   - 默认不自动打开浏览器，需用户显式输入 y 才打开

cd "$(dirname "$0")"
if [ $? -ne 0 ]; then
    echo "无法进入脚本所在目录"
    exit 1
fi

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

print_step() {
    echo ""
    echo -e "${CYAN}${BOLD}━━━━━ $1 ━━━━━${NC}"
}

print_ok() {
    echo -e "${GREEN}[v]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_err() {
    echo -e "${RED}[X]${NC} $1"
}

pause_exit() {
    echo ""
    read -n 1 -s -r -p "按任意键关闭..."
    exit $1
}

# ===========================================
# 开场
# ===========================================
clear
echo ""
echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}   森林小岛日报 · 首次部署向导${NC}"
echo -e "${BOLD}========================================${NC}"
echo ""
echo "本脚本会帮你完成："
echo "  1. 环境检查（git / python）"
echo "  2. 初始化 git 仓库"
echo "  3. 配置 GitHub 远端地址"
echo "  4. 首次提交并推送"
echo "  5. 给出 GitHub Pages 启用步骤"
echo ""
read -n 1 -s -r -p "按任意键开始..."

# ===========================================
# 步骤 0：前置确认 - 是否已创建 GitHub 仓库
# ===========================================
print_step "步骤 0 / 5：前置确认"
echo ""
echo -e "${YELLOW}重要：${NC}在继续前，请确认你已经在 GitHub 网页${BOLD}手动创建了一个空仓库${NC}。"
echo ""
echo "  → 打开：https://github.com/new"
echo "  → 仓库名建议：forest-island-daily"
echo "  → ${RED}不要${NC}勾选 README / .gitignore / license"
echo "  → 点击 Create repository"
echo ""
echo "如果跳过这步，后续 git push 会失败，浏览器也会跳到错误的页面。"
echo ""
read -p "你已经在 GitHub 创建好空仓库了吗？(y/N): " REPO_READY
case "$REPO_READY" in
    y|Y|yes|YES)
        print_ok "好的，继续"
        ;;
    *)
        echo ""
        print_err "请先去 https://github.com/new 创建空仓库，再重新运行本脚本"
        pause_exit 1
        ;;
esac

# ===========================================
# 步骤 1：环境检查
# ===========================================
print_step "步骤 1 / 5：环境检查"

command -v git >/dev/null 2>&1
if [ $? -ne 0 ]; then
    print_err "未找到 git"
    echo "请先安装 git："
    echo "  macOS: xcode-select --install"
    echo "  Windows: https://git-scm.com/download/win"
    pause_exit 1
fi
print_ok "git 已安装：$(git --version)"

command -v python3 >/dev/null 2>&1
if [ $? -ne 0 ]; then
    command -v python >/dev/null 2>&1
    if [ $? -ne 0 ]; then
        print_err "未找到 python"
        echo "请先安装 Python 3：https://www.python.org/downloads/"
        pause_exit 1
    fi
fi
print_ok "python 已安装"

MISSING=0
for f in index.html data/archive.json scripts/generate.py .github/workflows/daily.yml; do
    if [ ! -f "$f" ]; then
        print_err "缺少文件：$f"
        MISSING=1
    fi
done
if [ $MISSING -ne 0 ]; then
    print_err "项目文件不完整，请重新解压工程包"
    pause_exit 1
fi
print_ok "项目文件完整"

# ===========================================
# 步骤 2：git 用户配置
# ===========================================
print_step "步骤 2 / 5：检查 git 用户身份"

GIT_NAME=$(git config --global user.name)
GIT_EMAIL=$(git config --global user.email)

if [ -z "$GIT_NAME" ]; then
    echo ""
    read -p "请输入你的 GitHub 用户名（用于 commit 署名）: " GIT_NAME
    if [ -z "$GIT_NAME" ]; then
        print_err "用户名不能为空"
        pause_exit 1
    fi
    git config --global user.name "$GIT_NAME"
fi

if [ -z "$GIT_EMAIL" ]; then
    echo ""
    read -p "请输入你的 GitHub 邮箱: " GIT_EMAIL
    if [ -z "$GIT_EMAIL" ]; then
        print_err "邮箱不能为空"
        pause_exit 1
    fi
    git config --global user.email "$GIT_EMAIL"
fi

print_ok "git user.name  = $GIT_NAME"
print_ok "git user.email = $GIT_EMAIL"

# ===========================================
# 步骤 3：初始化 git 仓库
# ===========================================
print_step "步骤 3 / 5：初始化 git 仓库"

if [ -d ".git" ]; then
    print_warn "已存在 .git 目录，跳过初始化"
else
    git init
    if [ $? -ne 0 ]; then
        print_err "git init 失败"
        pause_exit 1
    fi
    print_ok "git init 完成"
fi

CURRENT_BRANCH=$(git branch --show-current)
if [ -z "$CURRENT_BRANCH" ]; then
    git checkout -b main 2>/dev/null
fi

if [ ! -f ".gitignore" ]; then
    cat > .gitignore <<'GITIGNORE'
.DS_Store
*.log
__pycache__/
*.pyc
.vscode/
.idea/
node_modules/
GITIGNORE
    print_ok "生成 .gitignore"
fi

# ===========================================
# 步骤 4：配置远端
# ===========================================
print_step "步骤 4 / 5：配置 GitHub 远端"

EXISTING_REMOTE=$(git remote get-url origin 2>/dev/null)

if [ -n "$EXISTING_REMOTE" ]; then
    echo ""
    print_warn "已配置远端：$EXISTING_REMOTE"
    read -p "是否替换？(y/N): " REPLACE
    case "$REPLACE" in
        y|Y)
            git remote remove origin
            EXISTING_REMOTE=""
            ;;
        *)
            ;;
    esac
fi

if [ -z "$EXISTING_REMOTE" ]; then
    echo ""
    echo "请粘贴你刚刚创建的 GitHub 仓库地址："
    echo ""
    echo "支持两种格式："
    echo "  HTTPS: https://github.com/你的用户名/forest-island-daily.git"
    echo "  SSH:   git@github.com:你的用户名/forest-island-daily.git"
    echo ""
    read -p "粘贴仓库地址: " REPO_URL

    if [ -z "$REPO_URL" ]; then
        print_err "地址不能为空"
        pause_exit 1
    fi

    git remote add origin "$REPO_URL"
    if [ $? -ne 0 ]; then
        print_err "添加远端失败"
        pause_exit 1
    fi
    print_ok "已添加远端：$REPO_URL"
fi

# ===========================================
# 步骤 5：提交 + 推送
# ===========================================
print_step "步骤 5 / 5：首次提交与推送"

git add .
if [ $? -ne 0 ]; then
    print_err "git add 失败"
    pause_exit 1
fi

EXISTING_COMMIT=$(git log --oneline 2>/dev/null | head -1)

if [ -z "$EXISTING_COMMIT" ]; then
    git commit -m "init: forest island daily"
    if [ $? -ne 0 ]; then
        print_err "首次 commit 失败"
        pause_exit 1
    fi
    print_ok "首次提交完成"
else
    git diff --cached --quiet
    if [ $? -ne 0 ]; then
        TODAY=$(date +%Y-%m-%d)
        git commit -m "update: $TODAY"
        if [ $? -ne 0 ]; then
            print_err "commit 失败"
            pause_exit 1
        fi
        print_ok "增量提交完成"
    else
        print_warn "无新变更，跳过 commit"
    fi
fi

echo ""
echo "正在推送到 GitHub（首次推送可能需要登录授权）..."
echo ""

git branch -M main 2>/dev/null

git push -u origin main
PUSH_RESULT=$?

if [ $PUSH_RESULT -ne 0 ]; then
    echo ""
    print_err "推送失败（不会打开浏览器）"
    echo ""
    echo "可能原因："
    echo "  1. 远端仓库不存在：去 https://github.com/new 创建空仓库"
    echo "  2. HTTPS 地址：弹窗需输入 GitHub 用户名 + Personal Access Token"
    echo "     生成 Token → https://github.com/settings/tokens"
    echo "  3. SSH 地址：需先配置 SSH key"
    echo "     教程 → https://docs.github.com/en/authentication/connecting-to-github-with-ssh"
    echo "  4. 网络问题：检查能否访问 github.com"
    echo ""
    echo "问题解决后可重新双击本脚本继续"
    pause_exit 1
fi

print_ok "推送成功！"

# ===========================================
# 收尾：GitHub Pages 启用引导
# ===========================================
REMOTE_URL=$(git remote get-url origin)
WEB_URL=${REMOTE_URL%.git}
WEB_URL=${WEB_URL#git@github.com:}
WEB_URL=${WEB_URL#https://github.com/}

OWNER=$(echo "$WEB_URL" | cut -d'/' -f1)
REPO=$(echo "$WEB_URL" | cut -d'/' -f2)

# 兜底校验：解析出来必须两段都不为空
if [ -z "$OWNER" ]; then
    print_err "无法从远端地址解析出用户名，请手动检查"
    echo "  远端地址：$REMOTE_URL"
    pause_exit 1
fi
if [ -z "$REPO" ]; then
    print_err "无法从远端地址解析出仓库名，请手动检查"
    echo "  远端地址：$REMOTE_URL"
    pause_exit 1
fi

PAGES_URL="https://github.com/$OWNER/$REPO/settings/pages"
ACTIONS_URL="https://github.com/$OWNER/$REPO/actions"
SITE_URL="https://$OWNER.github.io/$REPO/"

clear
echo ""
echo -e "${GREEN}${BOLD}========================================${NC}"
echo -e "${GREEN}${BOLD}   部署成功！还有最后一步${NC}"
echo -e "${GREEN}${BOLD}========================================${NC}"
echo ""
echo -e "${BOLD}解析出的仓库信息：${NC}"
echo "  用户名：$OWNER"
echo "  仓库名：$REPO"
echo ""
echo -e "${BOLD}请打开浏览器，启用 GitHub Pages：${NC}"
echo ""
echo "  1. 访问仓库设置页："
echo -e "     ${CYAN}$PAGES_URL${NC}"
echo ""
echo "  2. 在「Build and deployment」区："
echo "     Source 下拉选择 → 「GitHub Actions」"
echo ""
echo "  3. 等待 1-2 分钟自动部署"
echo ""
echo "  4. 部署完成后访问："
echo -e "     ${CYAN}$SITE_URL${NC}"
echo ""
echo -e "${BOLD}查看部署进度：${NC}"
echo "  $ACTIONS_URL"
echo ""
echo -e "${YELLOW}─────────────────────────────────────────${NC}"
echo ""
echo -e "${BOLD}从今天起的日常使用：${NC}"
echo "  - 每天 08:00 飞书会收到 Mira 发的 today.json"
echo "  - 把附件保存到 data/today.json"
echo "  - 双击 push-today.command（Mac）/ push-today.bat（Win）"
echo "  - 网页 1-2 分钟后自动更新"
echo ""
echo -e "${YELLOW}─────────────────────────────────────────${NC}"
echo ""

# 默认 N，需要显式输入 y 才打开；并且只在 macOS 上自动开
command -v open >/dev/null 2>&1
HAS_OPEN=$?

if [ $HAS_OPEN -eq 0 ]; then
    echo "是否现在打开 GitHub Pages 设置页？"
    echo "  - 输入 y 后回车 → 打开浏览器"
    echo "  - 直接回车或输入其他 → 不打开（你也可以手动复制上面的链接）"
    read -p "你的选择 (y/N): " OPEN_NOW
    case "$OPEN_NOW" in
        y|Y|yes|YES)
            open "$PAGES_URL"
            print_ok "已在浏览器中打开 Pages 设置页"
            ;;
        *)
            print_warn "未打开浏览器，请手动复制上面的链接访问"
            ;;
    esac
fi

echo ""
read -n 1 -s -r -p "按任意键关闭..."
echo ""
