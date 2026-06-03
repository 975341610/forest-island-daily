#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate.py —— 合并今日新增数据到 archive.json
- 读取 data/today.json（fetch_news.py 产物）
- 与 data/archive.json 去重合并（key = url）
- 按日期倒序回写 archive.json
- 同时按日期切分到 data/{YYYY-MM-DD}.json
- 不会删除老数据；老内容永远保留 → 同一聚合页面持续累积

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


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate(item):
    missing = REQUIRED_KEYS - set(item.keys())
    if missing:
        return f"missing keys: {missing}"
    if not isinstance(item["detail"], list) or not item["detail"]:
        return "detail must be non-empty list"
    if not item["url"].startswith(("http://", "https://")):
        return f"bad url: {item['url']}"
    return None


def merge(archive, today_new):
    """按 url 去重，老的 archive 永远不丢"""
    existing_urls = {n["url"] for n in archive}
    added, skipped, invalid = 0, 0, 0
    for n in today_new:
        err = validate(n)
        if err:
            print(f"  ✗ invalid: {n.get('title','?')[:30]} → {err}")
            invalid += 1
            continue
        if n["url"] in existing_urls:
            skipped += 1
            continue
        archive.append(n)
        existing_urls.add(n["url"])
        added += 1
    return archive, added, skipped, invalid


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

    archive, added, skipped, invalid = merge(archive, today_new)
    archive.sort(key=lambda x: (x["date"], x["id"]), reverse=True)

    print(f"\n✅ added   : {added}")
    print(f"⏭️  skipped : {skipped} (already in archive)")
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
