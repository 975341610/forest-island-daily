#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
github_fetcher.py —— 抓取 GitHub Trending Top 25 + 排名变化追踪

数据流：
1. 抓多语言 trending 页面（all/python/typescript/javascript/go/rust）
2. 合并去重，每个 repo 调 REST API 拉 stars/desc/topics/language/avatar
3. 与 rank-history.json 中昨日快照对比，计算 rank_change 和 new_stars_today
4. 写入：
   - data/channels/github/trending-today.json (今日 Top 25 完整数据)
   - data/channels/github/rank-history.json    (滚动 30 天排名快照)
   - data/channels/github/trending-week.json   (本周聚合, 周一重置)

使用：python scripts/fetchers/github_fetcher.py [--top N] [--gh-token TOKEN]
环境变量：GH_TOKEN (可选, 提高 REST API 限额到 5000/h)
"""
import json
import os
import re
import sys
import argparse
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta, timezone
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHANNEL_DIR = os.path.join(ROOT, "data", "channels", "github")
TRENDING_TODAY = os.path.join(CHANNEL_DIR, "trending-today.json")
RANK_HISTORY = os.path.join(CHANNEL_DIR, "rank-history.json")
TRENDING_WEEK = os.path.join(CHANNEL_DIR, "trending-week.json")

LANGS = ["", "python", "typescript", "javascript", "go", "rust"]
DEFAULT_TOP = 25
HISTORY_KEEP_DAYS = 30

UA = "Mozilla/5.0 (compatible; ForestIslandBot/1.0)"


def fetch_trending_page(lang=""):
    """抓一个 trending 页面，返回 [(repo, today_stars_str, desc), ...]"""
    url = f"https://github.com/trending{('/' + lang) if lang else ''}?since=daily"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", errors="ignore")

    out = []
    articles = re.findall(r'<article class="Box-row">(.*?)</article>', html, re.DOTALL)
    for a in articles:
        m = re.search(r'href="/([\w.-]+/[\w.-]+)"', a)
        if not m:
            continue
        repo = m.group(1)
        if repo.startswith("sponsors/"):
            continue
        # today stars: "1,234 stars today"
        m_today = re.search(r'(\d[\d,]*)\s+stars today', a)
        today_stars = int(m_today.group(1).replace(",", "")) if m_today else 0
        out.append({"repo": repo, "today_stars": today_stars})
    return out


def collect_trending(top_n=DEFAULT_TOP):
    """跨语言合并 trending, 按 today_stars 排序取 Top N"""
    seen = OrderedDict()
    for lang in LANGS:
        try:
            items = fetch_trending_page(lang)
        except Exception as e:
            print(f"  ✗ trending {lang or 'all'} failed: {e}")
            continue
        for it in items:
            r = it["repo"]
            if r not in seen or it["today_stars"] > seen[r]["today_stars"]:
                seen[r] = it
        print(f"  · fetched {lang or 'all':12s} → {len(items)} repos (cumulative {len(seen)})")
    ranked = sorted(seen.values(), key=lambda x: -x["today_stars"])[:top_n]
    return ranked


def fetch_repo_api(repo, gh_token=None):
    """调 REST API 拉 repo 元数据"""
    url = f"https://api.github.com/repos/{repo}"
    headers = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    if gh_token:
        headers["Authorization"] = f"Bearer {gh_token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
        return {
            "stars": d.get("stargazers_count", 0),
            "forks": d.get("forks_count", 0),
            "language": d.get("language"),
            "description": d.get("description", "") or "",
            "topics": d.get("topics", []) or [],
            "owner_avatar": d.get("owner", {}).get("avatar_url", ""),
            "owner_type": d.get("owner", {}).get("type", ""),  # User / Organization
            "html_url": d.get("html_url", f"https://github.com/{repo}"),
            "created_at": d.get("created_at", ""),
            "pushed_at": d.get("pushed_at", ""),
            "license": (d.get("license") or {}).get("spdx_id", ""),
        }
    except urllib.error.HTTPError as e:
        print(f"    API fail {repo}: {e.code}")
        return None


def load_rank_history():
    if os.path.exists(RANK_HISTORY):
        with open(RANK_HISTORY) as f:
            return json.load(f)
    return {"snapshots": {}}  # {date_str: {repo: rank}}


def prune_history(hist):
    """只保留最近 HISTORY_KEEP_DAYS 天"""
    cutoff = (date.today() - timedelta(days=HISTORY_KEEP_DAYS)).isoformat()
    hist["snapshots"] = {d: v for d, v in hist["snapshots"].items() if d >= cutoff}


def compute_rank_change(today_repos, hist):
    """与昨日快照对比, 给每条加 rank_change 字段
    - "↑5" / "↓3" / "NEW" / "—"
    """
    # 找昨日 (最近一个不等于今天的快照)
    today_str = date.today().isoformat()
    prev_dates = sorted([d for d in hist["snapshots"].keys() if d < today_str], reverse=True)
    if not prev_dates:
        for i, r in enumerate(today_repos):
            r["rank_change"] = "NEW"
            r["prev_rank"] = None
        return
    prev_snap = hist["snapshots"][prev_dates[0]]
    for i, r in enumerate(today_repos):
        cur_rank = i + 1
        prev_rank = prev_snap.get(r["repo"])
        r["prev_rank"] = prev_rank
        if prev_rank is None:
            r["rank_change"] = "NEW"
        else:
            delta = prev_rank - cur_rank  # 正=上升
            if delta == 0:
                r["rank_change"] = "—"
            elif delta > 0:
                r["rank_change"] = f"↑{delta}"
            else:
                r["rank_change"] = f"↓{-delta}"


def update_week_data(today_repos):
    """聚合本周 (周一开始) 出现过的 repo 及最高排名"""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    week_id = monday.isoformat()

    if os.path.exists(TRENDING_WEEK):
        with open(TRENDING_WEEK) as f:
            wk = json.load(f)
        if wk.get("week_start") != week_id:
            wk = {"week_start": week_id, "repos": {}}
    else:
        wk = {"week_start": week_id, "repos": {}}

    for i, r in enumerate(today_repos):
        cur_rank = i + 1
        repo = r["repo"]
        if repo not in wk["repos"]:
            wk["repos"][repo] = {
                "best_rank": cur_rank,
                "appearances": 1,
                "total_today_stars": r["today_stars"],
                "language": r.get("language"),
                "description": r.get("description", ""),
                "owner_avatar": r.get("owner_avatar", ""),
                "html_url": r.get("html_url", f"https://github.com/{repo}"),
            }
        else:
            entry = wk["repos"][repo]
            entry["best_rank"] = min(entry["best_rank"], cur_rank)
            entry["appearances"] += 1
            entry["total_today_stars"] += r["today_stars"]

    with open(TRENDING_WEEK, "w") as f:
        json.dump(wk, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=DEFAULT_TOP)
    parser.add_argument("--gh-token", default=os.environ.get("GH_TOKEN"))
    args = parser.parse_args()

    os.makedirs(CHANNEL_DIR, exist_ok=True)

    print(f"🔍 collecting trending across {len(LANGS)} pages...")
    ranked = collect_trending(args.top)
    print(f"\n📊 Top {len(ranked)} candidates:")
    for i, r in enumerate(ranked[:5]):
        print(f"  {i+1}. {r['repo']} (+{r['today_stars']} today)")
    print("  ...")

    print(f"\n🌐 fetching REST API for {len(ranked)} repos...")
    enriched = []
    for r in ranked:
        meta = fetch_repo_api(r["repo"], args.gh_token)
        if not meta:
            continue
        r.update(meta)
        enriched.append(r)
    print(f"  ✓ enriched {len(enriched)}/{len(ranked)}")

    hist = load_rank_history()
    compute_rank_change(enriched, hist)

    # 写今日快照
    today_str = date.today().isoformat()
    hist["snapshots"][today_str] = {r["repo"]: i + 1 for i, r in enumerate(enriched)}
    prune_history(hist)
    with open(RANK_HISTORY, "w") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)
    print(f"💾 wrote {RANK_HISTORY} ({len(hist['snapshots'])} day snapshots)")

    # 写今日 trending
    today_doc = {
        "date": today_str,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(enriched),
        "repos": enriched,
    }
    with open(TRENDING_TODAY, "w") as f:
        json.dump(today_doc, f, ensure_ascii=False, indent=2)
    print(f"💾 wrote {TRENDING_TODAY}")

    update_week_data(enriched)
    print(f"💾 wrote {TRENDING_WEEK}")

    print("\n🎉 done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
