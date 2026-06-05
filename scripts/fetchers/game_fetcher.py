#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
game_fetcher.py —— 游戏频道每日自动抓取（RSS 聚合兜底）

设计思路
--------
游戏新闻没有统一 API，散落在各大媒体/厂商博客。本脚本聚合一批
**稳定的 RSS 源**，抓取最近 24h 的条目，粗分类到 hot / studios，
保证页面每天「不空」。releases（发售时间表）因为 RSS 里没有结构化
的「发售日期 / 平台」字段，无法可靠自动提取，故采取保留策略：
脚本只更新 hot / studios，releases 沿用已有 today.json 中的人工/
半自动维护内容（由 Mira 调研流程升级）。

三层内容策略（与 GitHub 频道一致）
1. 本脚本（Actions 可无人值守）：RSS 抓 hot / studios 兜底
2. Mira 调研（手动触发「跑游戏日报」）：高质量改写 + 大白话 + releases
3. 前端：优先展示，字段缺失自动降级

数据流
1. 并发抓 RSS 源 → 解析 <item>（title / link / pubDate / description）
2. 过滤最近 LOOKBACK_HOURS 小时内的条目
3. 关键词分类：命中厂商名 → studios，其余 → hot
4. 去重（按归一化标题 + 链接）
5. 合并：保留旧 today.json 的 releases，覆盖 hot / studios
6. 写入 data/channels/game/game-today.json

用法
  python scripts/fetchers/game_fetcher.py [--max-hot N] [--max-studio N] [--lookback-hours H]
"""
import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html import unescape

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHANNEL_DIR = os.path.join(ROOT, "data", "channels", "game")
GAME_TODAY = os.path.join(CHANNEL_DIR, "game-today.json")

UA = "Mozilla/5.0 (compatible; ForestIslandBot/1.0; +game)"

# 稳定 RSS 源（媒体 + 厂商官方）
FEEDS = [
    ("IGN", "https://feeds.ign.com/ign/games-all"),
    ("GameSpot", "https://www.gamespot.com/feeds/game-news/"),
    ("Eurogamer", "https://www.eurogamer.net/feed"),
    ("Polygon", "https://www.polygon.com/rss/index.xml"),
    ("PC Gamer", "https://www.pcgamer.com/rss/"),
    ("Kotaku", "https://kotaku.com/rss"),
    ("VG247", "https://www.vg247.com/feed"),
    ("PlayStation Blog", "https://blog.playstation.com/feed/"),
    ("Xbox Wire", "https://news.xbox.com/en-us/feed/"),
    ("Nintendo Life", "https://www.nintendolife.com/feeds/latest"),
]

# 厂商关键词 → 归一化公司名（命中即进 studios）
STUDIO_KEYWORDS = {
    "索尼 / SIE": ["sony", "playstation", "sie ", "state of play"],
    "微软 / Xbox": ["xbox", "microsoft", "bethesda", "activision blizzard"],
    "任天堂": ["nintendo", "switch 2", "switch2"],
    "Take-Two / Rockstar": ["rockstar", "take-two", "take two", "gta", "grand theft auto"],
    "卡普空 / Capcom": ["capcom"],
    "Valve": ["valve", "steam deck", "steam machine", "steamos"],
    "育碧 / Ubisoft": ["ubisoft"],
    "EA / 美国艺电": ["electronic arts", "ea sports", "battlefield"],
    "Square Enix": ["square enix"],
    "世嘉 / SEGA": ["sega ", "atlus"],
    "Epic Games": ["epic games", "fortnite", "unreal engine"],
    "网易游戏": ["netease"],
    "腾讯游戏": ["tencent"],
}

# 分类标签关键词（用于 hot 的 category 字段）
CATEGORY_RULES = [
    ("发售定档", ["release date", "launches", "out now", "release window", "定档", "发售"]),
    ("爆料", ["leak", "rumor", "rumour", "report:", "datamine", "泄露", "爆料"]),
    ("游戏更新", ["update", "patch", "season ", "dlc", "expansion", "更新"]),
    ("行业活动", ["showcase", "direct", "summer game fest", "the game awards", "发布会"]),
    ("市场热点", ["sales", "best-selling", "charts", "revenue", "销量"]),
]


def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def strip_html(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    s = unescape(s).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def parse_items(xml, source):
    """解析 RSS/Atom，返回 [{title, link, pub, desc}]"""
    items = []
    # RSS <item> 或 Atom <entry>
    blocks = re.findall(r"<item\b.*?</item>", xml, re.DOTALL | re.IGNORECASE)
    is_atom = False
    if not blocks:
        blocks = re.findall(r"<entry\b.*?</entry>", xml, re.DOTALL | re.IGNORECASE)
        is_atom = True
    for b in blocks:
        t = re.search(r"<title\b[^>]*>(.*?)</title>", b, re.DOTALL | re.IGNORECASE)
        title = strip_html(re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", t.group(1), flags=re.DOTALL)) if t else ""
        if is_atom:
            l = re.search(r'<link[^>]*href="([^"]+)"', b, re.IGNORECASE)
            link = l.group(1) if l else ""
            d = re.search(r"<(?:updated|published)>(.*?)</(?:updated|published)>", b, re.DOTALL | re.IGNORECASE)
        else:
            l = re.search(r"<link\b[^>]*>(.*?)</link>", b, re.DOTALL | re.IGNORECASE)
            link = strip_html(l.group(1)) if l else ""
            d = re.search(r"<pubDate>(.*?)</pubDate>", b, re.DOTALL | re.IGNORECASE)
        pub = None
        if d:
            try:
                pub = parsedate_to_datetime(d.group(1).strip())
            except Exception:
                try:
                    pub = datetime.fromisoformat(d.group(1).strip().replace("Z", "+00:00"))
                except Exception:
                    pub = None
        if pub and pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        desc = re.search(r"<(?:description|summary|content)\b[^>]*>(.*?)</(?:description|summary|content)>",
                         b, re.DOTALL | re.IGNORECASE)
        desc = strip_html(re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", desc.group(1), flags=re.DOTALL)) if desc else ""
        if title and link:
            items.append({"title": title, "link": link, "pub": pub, "desc": desc[:280], "source": source})
    return items


def classify_studio(text):
    low = text.lower()
    for company, kws in STUDIO_KEYWORDS.items():
        if any(k in low for k in kws):
            return company
    return None


def classify_category(text):
    low = text.lower()
    for cat, kws in CATEGORY_RULES:
        if any(k in low for k in kws):
            return cat
    return "重磅新闻"


def norm(s):
    return re.sub(r"[^a-z0-9一-鿿]", "", (s or "").lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-hot", type=int, default=12)
    ap.add_argument("--max-studio", type=int, default=9)
    ap.add_argument("--lookback-hours", type=int, default=36)
    args = ap.parse_args()

    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.lookback_hours)
    all_items = []
    for source, url in FEEDS:
        try:
            xml = fetch(url)
            items = parse_items(xml, source)
            all_items.extend(items)
            print(f"  ✓ {source:20s} {len(items)} items", file=sys.stderr)
        except Exception as e:
            print(f"  ✗ {source:20s} {e}", file=sys.stderr)

    # 时间过滤（无 pubDate 的保留，按媒体靠前排）
    fresh = [it for it in all_items if (it["pub"] is None or it["pub"] >= cutoff)]
    fresh.sort(key=lambda it: it["pub"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    seen = set()
    hot, studios = [], []
    studio_companies = set()
    for it in fresh:
        key = norm(it["title"])[:60]
        if not key or key in seen:
            continue
        seen.add(key)
        company = classify_studio(it["title"] + " " + it["desc"])
        if company and company not in studio_companies and len(studios) < args.max_studio:
            studio_companies.add(company)
            studios.append({
                "company": company,
                "title": it["title"][:60],
                "summary": it["desc"] or it["title"],
                "source": it["source"],
                "url": it["link"],
            })
        elif len(hot) < args.max_hot:
            hot.append({
                "title": it["title"][:60],
                "category": classify_category(it["title"] + " " + it["desc"]),
                "summary": it["desc"] or it["title"],
                "source": it["source"],
                "url": it["link"],
            })
        if len(hot) >= args.max_hot and len(studios) >= args.max_studio:
            break

    # 合并：保留旧 releases（RSS 无法可靠产出发售表）
    releases = []
    if os.path.exists(GAME_TODAY):
        try:
            with open(GAME_TODAY, encoding="utf-8") as f:
                releases = json.load(f).get("releases", [])
        except Exception:
            releases = []

    doc = {
        "date": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "rss-auto",
        "releases": releases,
        "hot": hot,
        "studios": studios,
    }
    os.makedirs(CHANNEL_DIR, exist_ok=True)
    with open(GAME_TODAY, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print(f"✅ game-today.json: releases={len(releases)}(保留) hot={len(hot)} studios={len(studios)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
