#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate.py —— 合并今日新增数据到 archive.json
- 读取 data/today.json（fetch_news.py 产物）
- 与 data/archive.json 按 url 去重合并
  · 同 url 时保留 detail 更长的版本（支持对历史条目内容升级）
  · 不同 url 直接新增；老的 archive 不会丢
- 按日期倒序回写 archive.json
- 同时按日期切分到 data/{YYYY-MM-DD}.json
- detail 设有字数/段数硬门槛，过短的条目直接 invalid（参考 06-05 事故）

使用：python scripts/generate.py [--dry-run]
"""
import json, os, sys, argparse
from collections import defaultdict
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
ARCHIVE = os.path.join(DATA_DIR, "archive.json")
TODAY   = os.path.join(DATA_DIR, "today.json")

REQUIRED_KEYS = {"id", "date", "category", "subcat", "platform",
                 "platform_color", "title", "url", "image", "detail"}

# detail 质量门槛：每条新闻总字数不少于此值，段数不少于此数，否则视为不合格
DETAIL_MIN_CHARS = 350
DETAIL_MIN_SEGS = 3

# 各 category 对应的颜色（Animal Crossing 配色 + 平台主色）
CATEGORY_COLORS = {
    # AI 家族
    "ai-claude":   "#D97757",
    "ai-codex":    "#10A37F",
    "ai-gemini":   "#4285F4",
    "ai-grok":     "#000000",
    "ai-llama":    "#0866FF",
    "AI":          "#10A37F",
    # 科技榜
    "hackernews":  "#FF6600",
    "github":      "#24292F",
    "reddit":      "#FF4500",
    "x":           "#000000",
    "youtube":     "#FF0000",
    "linkedin":    "#0A66C2",
    "instagram":   "#E1306C",
    "facebook":    "#1877F2",
    # 中文
    "bilibili":    "#FB7299",
    "xiaohongshu": "#FF2442",
    "douyin":      "#161823",
    "weibo":       "#E6162D",
    # 游戏
    "主机游戏":     "#E60012",
    "steam":       "#1B2838",
    "Gaming":      "#E60012",
}


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_item(item):
    """
    把新 schema 字段（image_url / subcategory / category_label / source）
    映射成前端需要的旧 schema（image / subcat / platform / platform_color）。
    已经是旧 schema 的 item 原样返回。
    """
    out = dict(item)

    # image_url -> image
    if "image" not in out and "image_url" in out:
        out["image"] = out["image_url"]

    # subcategory -> subcat
    if "subcat" not in out and "subcategory" in out:
        out["subcat"] = out["subcategory"]

    # source -> platform；category_label 作为备选
    if "platform" not in out:
        out["platform"] = out.get("source") or out.get("category_label") or out.get("category", "")

    # platform_color：按 category 查表，找不到给默认绿色
    if "platform_color" not in out:
        cat = out.get("category", "")
        out["platform_color"] = CATEGORY_COLORS.get(cat, "#8ED16D")

    # detail：允许字符串，转为单段列表
    if isinstance(out.get("detail"), str):
        # 按段分割（双换行或单换行）
        paragraphs = [p.strip() for p in out["detail"].replace("\r\n", "\n").split("\n") if p.strip()]
        out["detail"] = paragraphs if paragraphs else [out["detail"]]

    return out


def detail_chars(item):
    """计算 detail 总字数（用于 URL 重复时择优）"""
    d = item.get("detail", [])
    if isinstance(d, list):
        return sum(len(x) for x in d if isinstance(x, str))
    if isinstance(d, str):
        return len(d)
    return 0


def validate(item):
    missing = REQUIRED_KEYS - set(item.keys())
    if missing:
        return f"missing keys: {missing}"
    if not isinstance(item["detail"], list) or not item["detail"]:
        return "detail must be non-empty list"
    if not item["url"].startswith(("http://", "https://")):
        return f"bad url: {item['url']}"
    # 字数与段数硬门槛：防止 detail 太短（参考 06-05 事故）
    total_chars = detail_chars(item)
    if total_chars < DETAIL_MIN_CHARS:
        return f"detail too short: {total_chars} chars (min {DETAIL_MIN_CHARS})"
    if len(item["detail"]) < DETAIL_MIN_SEGS:
        return f"detail too few segments: {len(item['detail'])} (min {DETAIL_MIN_SEGS})"
    return None


def merge(archive, today_new):
    """
    按 url 去重合并。
    策略：
    - 同 url 时保留 detail 更长的版本（支持对历史条目做内容升级）
    - 覆盖时保留原 id/date，避免日期文件错位
    - 不同 url 直接新增
    - 老 archive 不会丢
    """
    url_to_idx = {n["url"]: i for i, n in enumerate(archive)}
    added, updated, skipped, invalid = 0, 0, 0, 0
    for raw in today_new:
        n = normalize_item(raw)
        err = validate(n)
        if err:
            print(f"  ✗ invalid: {n.get('title','?')[:30]} → {err}")
            invalid += 1
            continue
        if n["url"] in url_to_idx:
            old = archive[url_to_idx[n["url"]]]
            if detail_chars(n) > detail_chars(old):
                # 覆盖式更新；保留原 id/date 防止日期切分错乱
                n["id"] = old.get("id", n["id"])
                n["date"] = old.get("date", n["date"])
                archive[url_to_idx[n["url"]]] = n
                updated += 1
                print(f"  🔄 updated: {n['title'][:30]} ({detail_chars(old)} → {detail_chars(n)} chars)")
            else:
                skipped += 1
            continue
        archive.append(n)
        url_to_idx[n["url"]] = len(archive) - 1
        added += 1
    return archive, added, updated, skipped, invalid


def split_by_date(archive):
    by_date = defaultdict(list)
    for n in archive:
        by_date[n["date"]].append(n)
    return by_date


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)
    archive = load_json(ARCHIVE, [])
    today_new = load_json(TODAY, [])

    print(f"📚 existing archive : {len(archive)} items")
    print(f"🆕 today new        : {len(today_new)} items")

    if not today_new:
        print("⚠️  today.json 为空或不存在，跳过合并")
        return 0

    archive, added, updated, skipped, invalid = merge(archive, today_new)
    archive.sort(key=lambda x: (x["date"], x["id"]), reverse=True)

    print(f"\n✅ added   : {added}")
    print(f"🔄 updated : {updated} (longer detail overwrote shorter)")
    print(f"⏭️  skipped : {skipped} (already in archive, not longer)")
    print(f"❌ invalid : {invalid}")
    print(f"📊 total   : {len(archive)} items")

    if args.dry_run:
        print("🧪 DRY RUN — no files written")
        return 0

    # 写 archive.json
    with open(ARCHIVE, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)
    print(f"💾 wrote {ARCHIVE}")

    # 按日期切分
    by_date = split_by_date(archive)
    for d, items in by_date.items():
        path = os.path.join(DATA_DIR, f"{d}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"💾 wrote {len(by_date)} per-date files")

    # 写一个 build_info.json（用于网页显示更新时间）
    info = {
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "total_items": len(archive),
        "total_dates": len(by_date),
        "latest_date": max(by_date.keys()) if by_date else None,
    }
    with open(os.path.join(DATA_DIR, "build_info.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    print("\n🎉 done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
