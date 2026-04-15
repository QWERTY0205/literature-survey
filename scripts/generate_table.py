#!/usr/bin/env python3
"""
Generate a comprehensive, flat table of ALL analyzed papers.

Unlike synthesize.py which produces a grouped-by-category survey, this script
produces a single flat table with extra columns for problem_type and method_type
auto-classification, plus distribution stats.

Usage:
    python3 generate_table.py --workspace /data/paper/<topic>/ --topic "流式视频理解"

Output:
    <workspace>/<TOPIC>_FULL_TABLE.md
"""
import argparse
import json
import re
from pathlib import Path
from collections import Counter, defaultdict


# ---------- Auto-classification rules ----------
PROBLEM_TYPES = [
    ("效率/成本", ["效率", "计算", "开销", "内存", "显存", "延迟", "flops", "推理速度",
                   "cache", "冗余", "压缩", "加速", "部署", "边缘", "轻量", "context长度"]),
    ("长上下文/长序列", ["长视频", "hour", "小时", "extra-long", "分钟级", "长时", "long-form",
                         "长期", "long-term", "extended", "long context", "long audio"]),
    ("时间/时序建模", ["时间", "时序", "temporal", "时间戳", "时间定位", "时间推理",
                       "动态", "帧序", "时空", "motion", "运动", "时间感知"]),
    ("幻觉/一致性", ["幻觉", "hallucin", "不一致", "不可靠", "错误回答", "一致性", "consistency",
                     "sycophan", "迎合"]),
    ("流式/实时/交互", ["流式", "在线", "实时", "streaming", "proactive", "主动", "交互",
                        "real-time", "online", "dialogue", "对话", "full-duplex", "全双工"]),
    ("推理/因果", ["推理", "reason", "因果", "causal", "常识", "commonsense",
                   "chain-of-thought", "cot", "多步", "abductive", "反事实"]),
    ("细粒度/对齐", ["细粒度", "fine-grained", "精细", "object-level", "region-level", "pixel",
                     "实例级", "instance", "spatial", "对齐", "align"]),
    ("数据/标注", ["数据不足", "标注", "annotation", "缺乏数据", "lack", "低资源", "零样本",
                   "few-shot", "zero-shot", "数据构造"]),
    ("泛化/迁移", ["泛化", "generaliz", "迁移", "transfer", "domain", "域", "跨域"]),
    ("能力空白", ["未被解决", "未探索", "缺乏", "无法", "尚未", "unexplored", "缺失", "gap"]),
    ("安全/隐私", ["隐私", "privacy", "安全", "safety", "攻击", "adversarial", "泄露",
                   "偏见", "bias", "deepfake", "attack", "defense"]),
    ("多模态融合", ["多模态", "multimodal", "multi-modal", "omni", "跨模态", "cross-modal",
                    "音视", "audio-visual", "vision-language"]),
]

METHOD_TYPES = [
    ("新架构/模块", ["模块", "层", "encoder", "decoder", "transformer", "attention", "mamba",
                    "expert", "moe", "rnn", "lstm", "tokenizer", "架构", "backbone",
                    "embedding", "adapter"]),
    ("记忆机制", ["memory", "记忆", "memory bank", "kv cache", "kv-cache", "缓存", "buffer",
                  "memory pool", "persistent", "event memory"]),
    ("Token 压缩/选择", ["压缩", "prune", "pruning", "merg", "drop", "select", "采样", "sampling",
                        "稀疏", "sparse", "token selection", "frame selection", "帧选"]),
    ("RL/强化学习", ["rl", "强化学习", "reinforcement", "grpo", "dpo", "ppo", "reward", "奖励",
                    "policy", "rlhf", "self-play", "r1", "dapo"]),
    ("SFT/微调", ["微调", "fine-tun", "sft", "instruction tun", "指令调", "lora", "adapter",
                  "adaptation", "post-training"]),
    ("对比学习", ["contrastive", "对比", "nt-xent", "infonce", "pair", "triplet"]),
    ("预训练", ["预训练", "pre-train", "pretrain", "pretraining", "from scratch"]),
    ("Agent/多步", ["agent", "agentic", "multi-step", "tool use", "工具", "plan",
                    "策划", "planner", "multi-agent", "多智能体", "react"]),
    ("Prompt/训练-free", ["training-free", "无需训练", "prompt", "zero-shot", "in-context",
                          "免训练", "无训练"]),
    ("检索增强/RAG", ["检索", "retriev", "rag", "retrieval-augmented", "搜索", "search"]),
    ("特殊Token化", ["special token", "特殊token", "token mark", "marker", "timestamp token",
                     "action token", "rdy"]),
    ("数据合成/蒸馏", ["合成数据", "synthetic", "自动标注", "auto-annotat", "数据构造",
                      "数据增强", "蒸馏", "distill"]),
    ("CoT/推理链", ["chain-of-thought", "cot", "推理链", "think step", "reasoning chain",
                    "多步推理", "verify"]),
    ("位置编码", ["position encoding", "位置编码", "rope", "timestamp", "positional"]),
    ("扩散/生成", ["diffusion", "扩散", "flow matching", "diffuse", "ddpm"]),
]


def classify(text: str, types: list) -> list:
    if not text:
        return []
    t = text.lower()
    matches = []
    for name, kws in types:
        for kw in kws:
            if kw in t:
                matches.append(name)
                break
    return matches


def esc(s) -> str:
    if not s:
        return ""
    return str(s).replace("|", "\\|").replace("\n", " ").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--topic", required=True)
    args = ap.parse_args()

    workspace = Path(args.workspace)

    # Load merged data (from synthesize.py) or merge results directly
    merged_file = workspace / "all_merged.json"
    if merged_file.exists():
        papers = json.load(open(merged_file))
    else:
        papers = []
        for f in sorted((workspace / "results").glob("b_*.json")):
            try:
                data = json.load(open(f))
                if isinstance(data, list):
                    papers.extend(data)
            except Exception:
                pass
        # Dedup
        seen = {}
        for p in papers:
            k = (p.get("title") or "").strip().lower()
            if k and k not in seen:
                seen[k] = p
        papers = list(seen.values())

    print(f"Loaded {len(papers)} papers")

    # Auto-classify each paper
    rows = []
    for p in papers:
        prob_text = p.get("problem", "") or ""
        meth_text = p.get("method", "") or ""
        p_types = classify(prob_text, PROBLEM_TYPES)
        m_types = classify(meth_text, METHOD_TYPES)
        rows.append({
            "title": p.get("title", ""),
            "source": p.get("venue_or_arxiv", p.get("source", "")),
            "category": p.get("category", "other"),
            "problem": prob_text,
            "problem_type": " / ".join(p_types[:3]) if p_types else "能力空白",
            "method": meth_text,
            "method_type": " / ".join(m_types[:3]) if m_types else "新架构/模块",
            "novelty": p.get("novelty", ""),
            "training": p.get("training_strategy", ""),
            "benchmark": p.get("benchmark_used", ""),
            "key_number": p.get("key_number", ""),
            "open_source": p.get("open_source") or "",
        })

    # Sort: category -> source
    rows.sort(key=lambda r: (r["category"], r["source"], r["title"]))

    # Stats
    cat_cnt = Counter(r["category"] for r in rows)
    prob_cnt = Counter()
    for r in rows:
        for t in r["problem_type"].split(" / "):
            if t:
                prob_cnt[t] += 1
    meth_cnt = Counter()
    for r in rows:
        for t in r["method_type"].split(" / "):
            if t:
                meth_cnt[t] += 1

    # Output
    out = workspace / f"{args.topic.replace(' ', '_')}_FULL_TABLE.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# {args.topic} — 完整论文总表 ({len(rows)} 篇)\n\n")
        f.write("> 每篇论文包含：问题 / 问题类型 / 方法 / 方法类型 / 训练策略 / Benchmark / 关键数字 / 开源\n\n")
        f.write("---\n\n")

        # Stats
        f.write("## 类别分布\n\n")
        f.write("| 类别 | 数量 |\n|------|------|\n")
        for c, n in cat_cnt.most_common():
            f.write(f"| {c} | {n} |\n")
        f.write(f"| **总计** | **{len(rows)}** |\n\n")

        f.write("## 问题类型分布\n\n")
        f.write("| 问题类型 | 论文数 |\n|---------|-------|\n")
        for c, n in prob_cnt.most_common():
            f.write(f"| {c} | {n} |\n")
        f.write("\n")

        f.write("## 方法类型分布\n\n")
        f.write("| 方法类型 | 论文数 |\n|---------|-------|\n")
        for c, n in meth_cnt.most_common():
            f.write(f"| {c} | {n} |\n")
        f.write("\n---\n\n")

        # Full flat table
        f.write("## 完整论文表\n\n")
        f.write("| # | 论文 | 来源 | 类别 | 问题 | 问题类型 | 方法 | 方法类型 | 训练 | Benchmark | 关键数字 | 开源 |\n")
        f.write("|---|------|------|------|------|---------|------|---------|------|-----------|---------|------|\n")
        for i, r in enumerate(rows, 1):
            title = esc(r["title"])
            os_ = r["open_source"]
            os_cell = f"[💾]({os_})" if os_ and "http" in str(os_) else ("有" if os_ else "")
            f.write(
                f"| {i} | {title} | {esc(r['source'])} | {esc(r['category'])} | "
                f"{esc(r['problem'])} | {esc(r['problem_type'])} | "
                f"{esc(r['method'])} | {esc(r['method_type'])} | "
                f"{esc(r['training'])[:30]} | {esc(r['benchmark'])[:60]} | "
                f"{esc(r['key_number'])[:80]} | {os_cell} |\n"
            )
        f.write("\n")

    print(f"\n✓ Full table: {out}")
    print(f"  {len(rows)} rows, {len(cat_cnt)} categories, {len(prob_cnt)} problem types, {len(meth_cnt)} method types")


if __name__ == "__main__":
    main()
