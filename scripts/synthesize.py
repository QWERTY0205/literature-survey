#!/usr/bin/env python3
"""
Merge per-batch results and generate the final survey markdown table.

Usage:
    python3 synthesize.py --workspace /data/paper/<topic>/ --topic "流式视频理解"

Outputs:
    <workspace>/<TOPIC>_SURVEY.md  — Full categorized paper table
    <workspace>/all_merged.json    — Structured data for all papers
"""
import argparse
import json
from pathlib import Path
from collections import Counter, defaultdict


def esc(s) -> str:
    if not s:
        return ""
    return str(s).replace("|", "\\|").replace("\n", " ").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--topic", required=True, help="Topic name for the report title")
    ap.add_argument("--category-names", type=str, default="",
                    help="Optional JSON string mapping category_slug to display name")
    args = ap.parse_args()

    workspace = Path(args.workspace)
    results_dir = workspace / "results"

    if not results_dir.exists():
        print("No results/ directory. Run the analysis agents first.")
        return

    # Load all batch results
    all_papers = []
    for f in sorted(results_dir.glob("b_*.json")):
        try:
            data = json.load(open(f))
            if isinstance(data, list):
                all_papers.extend(data)
        except Exception as e:
            print(f"  skip {f}: {e}")

    print(f"Loaded {len(all_papers)} papers")

    # Dedup by title
    seen = {}
    for p in all_papers:
        k = (p.get("title") or "").strip().lower()
        if k and k not in seen:
            seen[k] = p
    all_papers = list(seen.values())
    print(f"After dedup: {len(all_papers)}")

    # Save merged JSON
    json.dump(all_papers, open(workspace / "all_merged.json", "w"),
              ensure_ascii=False, indent=2)

    # Stats
    cats = Counter(p.get("category", "other") for p in all_papers)
    trains = Counter()
    for p in all_papers:
        ts = str(p.get("training_strategy", "") or "").lower()
        if any(k in ts for k in ["rl", "grpo", "dpo", "ppo", "rlhf"]):
            trains["RL/GRPO/DPO"] += 1
        elif "training-free" in ts or "无训练" in ts:
            trains["Training-free"] += 1
        elif "sft" in ts or "fine-tun" in ts or "微调" in ts:
            trains["SFT"] += 1
        elif "pre-train" in ts or "预训" in ts:
            trains["Pre-training"] += 1
        else:
            trains["其他"] += 1

    sources = Counter(p.get("source", "") for p in all_papers)

    print("\n=== Categories ===")
    for c, n in cats.most_common():
        print(f"  {c}: {n}")
    print("\n=== Training ===")
    for c, n in trains.most_common():
        print(f"  {c}: {n}")

    # Optional category display names (user-provided)
    cat_names = {}
    if args.category_names:
        try:
            cat_names = json.loads(args.category_names)
        except Exception:
            pass

    # Group by category
    by_cat = defaultdict(list)
    for p in all_papers:
        by_cat[p.get("category", "other")].append(p)

    # Write markdown
    out = workspace / f"{args.topic.replace(' ', '_')}_SURVEY.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# {args.topic} — Literature Survey ({len(all_papers)} papers)\n\n")
        f.write(f"> Full PDF深度阅读，全部来自 pdftotext 提取的完整正文\n\n")
        f.write("---\n\n## 类别分布\n\n")
        f.write("| 类别 | 数量 |\n|------|------|\n")
        for c, n in cats.most_common():
            name = cat_names.get(c, c)
            f.write(f"| {name} | {n} |\n")
        f.write(f"| **总计** | **{len(all_papers)}** |\n\n")

        f.write("## 训练策略分布\n\n")
        f.write("| 策略 | 数量 |\n|------|------|\n")
        for c, n in trains.most_common():
            f.write(f"| {c} | {n} |\n")
        f.write("\n")

        f.write("## 来源\n\n")
        f.write("| 来源 | 数量 |\n|------|------|\n")
        for c, n in sources.most_common():
            f.write(f"| {c} | {n} |\n")
        f.write("\n---\n\n## 按方向分类的论文总表\n\n")

        for c in sorted(by_cat.keys(), key=lambda k: -len(by_cat[k])):
            papers = by_cat[c]
            name = cat_names.get(c, c)
            f.write(f"### {name} ({len(papers)}篇)\n\n")
            f.write("| # | 论文 | 来源 | 问题 | 方法 | 训练 | 关键数字 | 开源 |\n")
            f.write("|---|------|------|------|------|------|---------|------|\n")
            for i, p in enumerate(papers, 1):
                title = esc(p.get("title", ""))
                src = esc(p.get("venue_or_arxiv", ""))
                prob = esc(p.get("problem", ""))
                meth = esc(p.get("method", ""))
                tr = esc(p.get("training_strategy", ""))[:30]
                kn = esc(p.get("key_number", ""))[:80]
                os_ = p.get("open_source") or ""
                os_cell = f"[💾]({os_})" if os_ and "http" in str(os_) else ("有" if os_ else "")
                f.write(f"| {i} | {title} | {src} | {prob} | {meth} | {tr} | {kn} | {os_cell} |\n")
            f.write("\n")

    print(f"\n✓ Report: {out}")
    print(f"✓ JSON:   {workspace / 'all_merged.json'}")
    print(f"\nNext: write the SYNTHESIS report with insights and research ideas.")
    print(f"      See references/synthesis_template.md")


if __name__ == "__main__":
    main()
