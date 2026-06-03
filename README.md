# 森林小岛日报 🌴 Forest Island Daily

每日自动聚合全球 **AI / 科技 / Vibe Coding / 游戏** 热点的静态网站，Animal Crossing 灵感设计。

## ✨ 特性

- 📱 **移动优先**：完美适配手机浏览，桌面端同样美观
- 📅 **日期归档**：所有往期内容永不丢失，按日期筛选回顾
- 📸 **小红书/抖音分享**：一键生成 3:4 竖屏分页图 + 平台文案
- ⬇️ **批量下载**：勾选图片后单张/ZIP 打包下载
- 🔄 **每日自动更新**：GitHub Actions 定时抓取 + 去重合并 + 部署
- 🌐 **GitHub Pages 托管**：永久免费 URL，无需服务器

## 🚀 部署步骤（5 分钟）

### 1. 推送到 GitHub

```bash
cd forest-island-daily
git init
git add .
git commit -m "🎉 init: forest island daily"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/forest-island-daily.git
git push -u origin main
```

### 2. 开启 GitHub Pages

1. 进入仓库 → **Settings** → **Pages**
2. Source 选择 **GitHub Actions**（不需要选分支）
3. 等待首次 Action 运行完成（约 1 分钟）
4. 访问 `https://YOUR_USERNAME.github.io/forest-island-daily/`

### 3. 可选：绑定自定义域名

1. Settings → Pages → Custom domain 填入你的域名
2. DNS 添加 CNAME 记录指向 `YOUR_USERNAME.github.io`
3. 勾选 Enforce HTTPS

## 📂 项目结构

```
forest-island-daily/
├── index.html              # 主页面（运行时 fetch archive.json）
├── data/
│   ├── archive.json        # 全量归档（按日期倒序）
│   ├── today.json          # 当天新抓取（CI 自动生成）
│   ├── build_info.json     # 构建元信息
│   └── 2026-06-03.json     # 按日期切分的文件
├── scripts/
│   ├── fetch_news.py       # 抓取脚本（接入你的数据源）
│   └── generate.py         # 合并去重脚本
├── assets/                 # 静态资源（可选）
├── .github/workflows/
│   └── daily.yml           # 定时任务 + 自动部署
└── README.md
```

## 🔧 自定义数据源

编辑 `scripts/fetch_news.py` 的 `collect_from_sources()` 函数：

```python
def collect_from_sources():
    items = []
    # 接入你的数据源，例如：
    # - HackerNews API（已内置示例）
    # - GitHub Trending RSS
    # - Twitter/X API
    # - 微博/小红书爬虫
    # - RSS Feed 聚合
    return items
```

每条数据需符合 schema：

```json
{
  "id": "n_2026-06-04_01",
  "date": "2026-06-04",
  "category": "AI",
  "subcat": "Claude",
  "platform": "X",
  "platform_color": "#1DA1F2",
  "title": "标题",
  "url": "https://...",
  "image": "https://... (1:1 封面图)",
  "detail": ["段落1", "段落2", "段落3"]
}
```

## 🕐 更新机制

| 时间 | 动作 |
|------|------|
| 每天 06:00 (北京时间) | GitHub Actions 自动触发 |
| `fetch_news.py` | 从各平台抓取今日热点 → `data/today.json` |
| `generate.py` | 去重合并到 `data/archive.json` + 按日期切分 |
| 自动提交 + 部署 | 新数据 push → Pages 自动重新部署 |

手动触发：仓库 → Actions → Daily Fetch & Deploy → Run workflow

## 🗑️ 去重逻辑

以 `url` 为唯一键，已存在于 `archive.json` 中的 URL 不会重复添加。老内容永远保留。

## 📜 License

MIT
