#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cn_enrich.py —— GitHub Trending 中文大白话富化

设计：fetcher 只抓英文原始数据，本脚本负责把 LLM 生成的中文解读写回。
LLM 调用由 Mira（Agent）在每日流程中完成，本脚本只做 I/O 与合并，
不直接调用任何模型（GitHub Actions 环境无法调 LLM）。

字段（写回到 trending-today.json 每个 repo）：
- cn_tagline : 一句话定位（≤14 字，如 "AI 编程助手"）
- cn_summary : 大白话介绍（2-3 句，可含 <b>强调</b>，说清"是什么 + 解决什么问题"）
- cn_who     : 适合谁用（一句话，如 "想让 AI 帮忙写代码的开发者"）
- cn_topics  : 中文话题标签（英文 topics 的中文化，≤5 个）

用法：
  # 1) 导出缺中文的条目（给 Agent 翻译）
  python scripts/fetchers/cn_enrich.py --list-missing > missing.json

  # 2) Agent 产出 enriched.json 后合并回去（按 repo 匹配）
  python scripts/fetchers/cn_enrich.py --merge enriched.json

  # 检查覆盖率
  python scripts/fetchers/cn_enrich.py --status
"""
import json
import os
import sys
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRENDING_TODAY = os.path.join(ROOT, "data", "channels", "github", "trending-today.json")

CN_FIELDS = ["cn_tagline", "cn_summary", "cn_who", "cn_topics"]


def load_today():
    with open(TRENDING_TODAY, encoding="utf-8") as f:
        return json.load(f)


def save_today(doc):
    with open(TRENDING_TODAY, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)


def has_cn(r):
    return bool(r.get("cn_summary")) and bool(r.get("cn_tagline"))


def cmd_list_missing(doc):
    """导出还没中文解读的条目，喂给 Agent 翻译"""
    out = []
    for r in doc.get("repos", []):
        if not has_cn(r):
            out.append({
                "repo": r["repo"],
                "description": r.get("description", ""),
                "language": r.get("language", ""),
                "topics": r.get("topics", [])[:8],
                "stars": r.get("stars", 0),
            })
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    print(file=sys.stderr)
    print(f"📋 {len(out)} repos 待中文化（共 {len(doc.get('repos', []))}）", file=sys.stderr)


def cmd_merge(doc, enriched_path):
    """把 Agent 产出的中文结果按 repo 名合并回 trending-today.json"""
    with open(enriched_path, encoding="utf-8") as f:
        enriched = json.load(f)
    by_repo = {e["repo"]: e for e in enriched}
    merged = 0
    for r in doc.get("repos", []):
        e = by_repo.get(r["repo"])
        if not e:
            continue
        for k in CN_FIELDS:
            if e.get(k):
                r[k] = e[k]
        merged += 1
    save_today(doc)
    print(f"✅ 合并 {merged} 条中文解读 → {TRENDING_TODAY}")


def cmd_status(doc):
    repos = doc.get("repos", [])
    done = sum(1 for r in repos if has_cn(r))
    print(f"📊 中文覆盖率：{done}/{len(repos)}")
    for r in repos:
        flag = "✓" if has_cn(r) else "✗"
        print(f"  {flag} {r['repo']:45s} {r.get('cn_tagline','—')}")


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--list-missing", action="store_true")
    g.add_argument("--merge", metavar="ENRICHED_JSON")
    g.add_argument("--status", action="store_true")
    args = ap.parse_args()

    doc = load_today()
    if args.list_missing:
        cmd_list_missing(doc)
    elif args.merge:
        cmd_merge(doc, args.merge)
    elif args.status:
        cmd_status(doc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
