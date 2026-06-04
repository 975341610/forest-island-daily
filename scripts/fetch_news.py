#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_news.py —— 每日抓取新热点，写入 data/today.json

⚙️  本脚本是"插槽式"骨架：
    - 默认会从 sources/*.py 收集器中聚合数据
    - 收集失败时退化为 mock 数据，保证 CI 不会断
    - 你可以自己接入：HackerNews API / GitHub Trending / RSS / 自有爬虫

📦 输出格式（与 archive.json 同 schema）：
    [
      {
        "id":            "n_2026-06-04_01",
        "date":          "2026-06-04",
        "category":      "AI" | "VibeCoding" | "Gaming",
        "subcat":        "Claude/Codex/Gemini/国产大模型/Steam新作/...",
        "platform":      "X" | "GitHub" | "Reddit" | "小红书" | ...,
        "platform_color":"#1DA1F2",
        "title":         "...",
        "url":           "https://...",
        "image":         "https://... (1:1 cover)",
        "detail":        ["段落1", "段落2", "段落3"]
      }
    ]
"""
import json, os, sys, hashlib
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
TODAY = os.path.join(DATA_DIR, "today.json")

# 北京时间 today
def beijing_today():
    return (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%d")


# === 各平台颜色（与卡片标签同步） ===
PLATFORM_COLORS = {
    "X": "#1DA1F2", "Twitter": "#1DA1F2",
    "GitHub": "#24292E", "Reddit": "#FF4500",
    "YouTube": "#FF0000", "TikTok": "#000000",
    "Instagram": "#E1306C", "LinkedIn": "#0077B5",
    "Pinterest": "#E60023", "Facebook": "#1877F2",
    "小红书": "#FE2C55", "抖音": "#161823",
    "微博": "#E6162D", "B站": "#FB7299", "哔哩哔哩": "#FB7299",
    "百度": "#2932E1", "今日头条": "#F04142",
    "Steam": "#1B2838", "Epic": "#2A2A2A",
    "Anthropic": "#D97757", "OpenAI": "#10A37F", "Google": "#4285F4",
    "官方博客": "#8ED16D",
}


def make_id(date, idx):
    return f"n_{date}_{str(idx).zfill(2)}"


# === 收集器接口（你可以扩展） ===
def collect_from_sources():
    """
    在这里接入你的真实数据源。
    返回 list[dict]，每条符合 schema。
    失败抛异常，外层会兜底成 mock。
    """
    items = []
    # === 示例 1：HackerNews top（公开 API，无需 token） ===
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            headers={"User-Agent": "forest-island-daily/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            ids = json.load(r)[:5]
        for hn_id in ids:
            try:
                req2 = urllib.request.Request(
                    f"https://hacker-news.firebaseio.com/v0/item/{hn_id}.json",
                    headers={"User-Agent": "forest-island-daily/1.0"})
                with urllib.request.urlopen(req2, timeout=10) as r:
                    s = json.load(r)
                if not s or s.get("type") != "story" or not s.get("url"):
                    continue
                items.append({
                    "platform_raw": "HackerNews",
                    "url": s["url"],
                    "title": s.get("title", "")[:120],
                    "score": s.get("score", 0),
                })
            except Exception:
                continue
    except Exception as e:
        print(f"⚠️  HN fetch failed: {e}")
    return items


def normalize_to_schema(raw_items, today):
    """把原始抓取条目转换成 archive schema"""
    out = []
    for i, x in enumerate(raw_items, start=1):
        plat = x.get("platform_raw", "官方博客")
        item = {
            "id":             make_id(today, i),
            "date":           today,
            "category":       x.get("category", "AI"),
            "subcat":         x.get("subcat", "全球科技热榜"),
            "platform":       plat,
            "platform_color": PLATFORM_COLORS.get(plat, "#8ED16D"),
            "title":          x["title"],
            "url":            x["url"],
            "image":          x.get("image") or
                              f"https://api.dicebear.com/7.x/shapes/png?seed={hashlib.md5(x['url'].encode()).hexdigest()[:8]}&size=512",
            "detail": x.get("detail") or [
                f"来自 {plat} 的今日热门内容：{x['title']}",
                "本条由自动抓取脚本汇入森林小岛日报，原文请点击链接查看；明日 06:00 会继续追加新条目，旧内容自动归档保留。",
            ],
        }
        out.append(item)
    return out


def make_mock(today):
    """CI 兜底：保证 today.json 始终非空"""
    return [{
        "id":             make_id(today, 1),
        "date":           today,
        "category":       "AI",
        "subcat":         "占位",
        "platform":       "官方博客",
        "platform_color": "#8ED16D",
        "title":          f"🌴 {today} · 今日热点抓取占位",
        "url":            "https://example.com/forest-island-daily",
        "image":          "https://api.dicebear.com/7.x/shapes/png?seed=island&size=512",
        "detail": [
            "fetch_news.py 暂未接入真实数据源，本条为占位以保证流水线不中断。",
            "请在 scripts/fetch_news.py 的 collect_from_sources() 函数内实现你自己的抓取逻辑。",
        ],
    }]


def main():
    today = beijing_today()
    print(f"📅 fetching for: {today}")

    # === 🛡️ 防覆盖保险：若 today.json 已是今天的高质量真数据，跳过抓取 ===
    if os.path.exists(TODAY):
        try:
            with open(TODAY, encoding="utf-8") as _f:
                _existing = json.load(_f)
            if isinstance(_existing, list) and len(_existing) >= 10:
                _today_items = [x for x in _existing if x.get("date") == today]
                if len(_today_items) >= 10:
                    _fake_markers = ("dicebear", "picsum", "placehold")
                    _fakes = sum(1 for x in _today_items
                                 if any(m in (x.get("image") or "") for m in _fake_markers))
                    _real = len(_today_items) - _fakes
                    if _real >= 10:
                        print(f"🛡️  today.json already has {_real} real items for {today}, skip overwrite")
                        return 0
        except Exception as _e:
            print(f"⚠️  guard check failed ({_e}), proceeding with fetch")
    # === 保险结束 ===

    try:
        raw = collect_from_sources()
        items = normalize_to_schema(raw, today)
        if not items:
            print("⚠️  no items collected, using mock")
            items = make_mock(today)
    except Exception as e:
        print(f"❌ fetch error: {e}, fallback to mock")
        items = make_mock(today)

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TODAY, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"✅ wrote {len(items)} items → {TODAY}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
