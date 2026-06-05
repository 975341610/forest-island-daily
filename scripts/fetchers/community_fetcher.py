#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
community_fetcher.py —— 社区频道每日自动抓取 + 归档（RSS 聚合兜底）

设计思路（与 game_fetcher 一致的三层内容策略）
------------------------------------------------
中文社区（小红书/抖音/B站/微博/知乎）没有统一开放 API，且大量内容反爬。
本脚本聚合一批**稳定可公开抓取的中文科技/数码/游戏 RSS 源**，抓最近
LOOKBACK_HOURS 小时条目，粗分类为 hot_posts / topics，保证页面每天「不空」。
creators（优质创作者）是相对稳定的推荐位，RSS 无法可靠产出，故沿用旧
community-today.json 中的人工/半自动维护内容（由 Mira「跑社区日报」升级）。

三层内容策略
1. 本脚本（Actions 无人值守）：RSS 抓 hot_posts / topics 兜底
2. Mira 调研（手动触发「跑社区日报」）：高质量真实热帖 + 话题 + 创作者
3. 前端：优先展示，字段缺失自动降级

归档（C 能力）
- 每次写完 community-today.json 后，按 date 快照到 archive/{date}.json
- 维护 index.json = {dates:[...倒序...], latest, total}
- 前端日期下拉读 index.json，切历史日期时 fetch 对应快照

用法
  python scripts/fetchers/community_fetcher.py [--max-posts N] [--max-topics N] [--lookback-hours H]
  python scripts/fetchers/community_fetcher.py --archive-only   # 仅按当前 today.json 归档(不抓取)
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html import unescape

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHANNEL_DIR = os.path.join(ROOT, "data", "channels", "community")
TODAY = os.path.join(CHANNEL_DIR, "community-today.json")
ARCHIVE_DIR = os.path.join(CHANNEL_DIR, "archive")
INDEX = os.path.join(CHANNEL_DIR, "index.json")

UA = "Mozilla/5.0 (compatible; ForestIslandBot/1.0; +community)"

# 稳定中文科技/数码/游戏 RSS 源（公开可抓，覆盖社区在聊的话题面）
FEEDS = [
    ("少数派", "https://sspai.com/feed"),
    ("36氪", "https://36kr.com/feed"),
    ("爱范儿", "https://www.ifanr.com/feed"),
    ("机核 GCORES", "https://www.gcores.com/rss"),
    ("游研社", "https://www.yystv.cn/rss/feed"),
    ("品玩 PingWest", "https://www.pingwest.com/feed"),
    ("雷锋网", "https://www.leiphone.com/feed"),
    ("InfoQ 中文", "https://www.infoq.cn/feed"),
]

# 平台归属推断（按来源/关键词给一个展示平台标签）
def guess_platform(text):
    low = text.lower()
    if any(k in text for k in ["B站", "哔哩", "bilibili", "up主", "UP主"]) or "bilibili" in low:
        return "B站"
    if any(k in text for k in ["小红书", "种草", "笔记"]):
        return "小红书"
    if any(k in text for k in ["抖音", "短视频"]):
        return "抖音"
    if "微博" in text or "热搜" in text:
        return "微博"
    if "知乎" in text:
        return "知乎"
    return "微博"  # 默认归到话题感最强的微博

# 话题关键词：命中即视为「热门话题」，其余进「热帖」
TOPIC_KEYWORDS = [
    "AI", "大模型", "GPT", "Claude", "Gemini", "DeepSeek", "Sora", "Seedance",
    "苹果", "WWDC", "iPhone", "安卓", "鸿蒙", "华为", "小米",
    "游戏", "Steam", "GTA", "主机", "显卡", "芯片", "存储",
    "开源", "编程", "开发者", "副业", "创作者",
]

# 标签归类
def guess_tag(text):
    low = text.lower()
    if any(k in text for k in ["AI", "大模型", "GPT", "Claude", "Gemini", "DeepSeek", "Sora", "Seedance", "智能体"]) or "ai" in low:
        return "AI工具"
    if any(k in text for k in ["游戏", "Steam", "GTA", "主机", "玩家"]):
        return "游戏资讯"
    if any(k in text for k in ["iPhone", "安卓", "鸿蒙", "手机", "芯片", "显卡", "数码", "评测"]):
        return "数码评测"
    if any(k in text for k in ["开源", "编程", "代码", "开发者"]):
        return "开发者"
    return "科技热点"


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
    items = []
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
            items.append({"title": title, "link": link, "pub": pub, "desc": desc[:300], "source": source})
    return items


def norm(s):
    return re.sub(r"[^a-z0-9一-鿿]", "", (s or "").lower())


def is_topic(text):
    return any(k.lower() in text.lower() for k in TOPIC_KEYWORDS)


def write_archive_and_index(doc):
    """把当天 doc 快照到 archive/{date}.json，并刷新 index.json"""
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    date = doc.get("date")
    if not date:
        return
    snap = os.path.join(ARCHIVE_DIR, f"{date}.json")
    with open(snap, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    # 扫描 archive 目录构建 index
    dates = []
    for fn in os.listdir(ARCHIVE_DIR):
        m = re.match(r"^(\d{4}-\d{2}-\d{2})\.json$", fn)
        if m:
            dates.append(m.group(1))
    dates = sorted(set(dates), reverse=True)
    index = {
        "dates": dates,
        "latest": dates[0] if dates else None,
        "total": len(dates),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(INDEX, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"📚 archived {date} → {snap}; index dates={len(dates)}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-posts", type=int, default=8)
    ap.add_argument("--max-topics", type=int, default=6)
    ap.add_argument("--lookback-hours", type=int, default=36)
    ap.add_argument("--archive-only", action="store_true",
                    help="不抓取，仅按当前 community-today.json 做归档/刷新 index")
    args = ap.parse_args()

    # 仅归档模式：直接读现有 today.json 快照
    if args.archive_only:
        if not os.path.exists(TODAY):
            print("⚠️  community-today.json 不存在，跳过", file=sys.stderr)
            return 0
        with open(TODAY, encoding="utf-8") as f:
            doc = json.load(f)
        write_archive_and_index(doc)
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.lookback_hours)
    all_items = []
    for source, url in FEEDS:
        try:
            xml = fetch(url)
            items = parse_items(xml, source)
            all_items.extend(items)
            print(f"  ✓ {source:14s} {len(items)} items", file=sys.stderr)
        except Exception as e:
            print(f"  ✗ {source:14s} {e}", file=sys.stderr)

    fresh = [it for it in all_items if (it["pub"] is None or it["pub"] >= cutoff)]
    fresh.sort(key=lambda it: it["pub"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    seen = set()
    hot_posts, topics = [], []
    topic_seen = set()
    for it in fresh:
        text = it["title"] + " " + it["desc"]
        key = norm(it["title"])[:60]
        if not key or key in seen:
            continue
        seen.add(key)
        if is_topic(text) and len(topics) < args.max_topics:
            tname = it["title"][:24]
            tk = norm(tname)
            if tk in topic_seen:
                continue
            topic_seen.add(tk)
            topics.append({
                "name": "#" + tname + "#",
                "platform": it["source"],
                "heat": "社区热议",
                "summary": it["desc"] or it["title"],
                "url": it["link"],
            })
        elif len(hot_posts) < args.max_posts:
            hot_posts.append({
                "platform": guess_platform(text),
                "title": it["title"][:30],
                "author": it["source"],
                "summary": it["desc"] or it["title"],
                "heat": "近期热门",
                "tag": guess_tag(text),
                "url": it["link"],
            })
        if len(hot_posts) >= args.max_posts and len(topics) >= args.max_topics:
            break

    # 沿用旧 creators（RSS 无法可靠产出推荐创作者）
    creators = []
    if os.path.exists(TODAY):
        try:
            with open(TODAY, encoding="utf-8") as f:
                creators = json.load(f).get("creators", [])
        except Exception:
            creators = []

    doc = {
        "date": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "rss-auto",
        "hot_posts": hot_posts,
        "topics": topics,
        "creators": creators,
    }
    os.makedirs(CHANNEL_DIR, exist_ok=True)
    with open(TODAY, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print(f"✅ community-today.json: posts={len(hot_posts)} topics={len(topics)} creators={len(creators)}(保留)", file=sys.stderr)

    write_archive_and_index(doc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
