#!/usr/bin/env python3
"""
Render findings.json + ideas.json + lineages.json into the final SYNTHESIS.md.

This is a *mechanical* renderer — it does NOT generate new content. The content
must already exist in the structured JSON files. This separation means:
  - findings/ideas are produced by Claude in a fresh-context session
  - verify_synthesis.py validates them before rendering
  - render_synthesis.py deterministically produces the markdown

Usage:
    python3 render_synthesis.py --workspace /data/paper/<topic>/ --topic "<TOPIC>"

Output:
    <workspace>/<TOPIC>_SYNTHESIS.md
"""
import argparse
import json
from pathlib import Path


def load_optional(path):
    if path.exists():
        return json.load(open(path))
    return None


def esc(s):
    if not s:
        return ""
    return str(s).replace("\n", " ").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--topic", required=True)
    args = ap.parse_args()

    workspace = Path(args.workspace)
    papers = load_optional(workspace / "all_merged.json") or []
    lineages = load_optional(workspace / "lineages.json") or {}
    findings = load_optional(workspace / "findings.json") or []
    ideas = load_optional(workspace / "ideas.json") or []

    if not findings and not ideas:
        print("No findings.json or ideas.json found. Generate these via Claude first.")
        return

    out = workspace / f"{args.topic.replace(' ', '_')}_SYNTHESIS.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# {args.topic} — Synthesis & Research Ideas\n\n")
        f.write(f"> Grounded in **{len(papers)} papers** (see `all_merged.json`)\n")
        f.write(f"> {len(lineages)} categories with lineage traces\n")
        f.write(f"> {len(findings)} cross-paper findings, {len(ideas)} lineage-grounded ideas\n\n")
        f.write("---\n\n")

        # --- Findings ---
        if findings:
            f.write("## Cross-Paper Findings\n\n")
            for i, fi in enumerate(findings, 1):
                f.write(f"### 🔥 Finding {i}: {esc(fi.get('title','(no title)'))}\n\n")
                ppl = fi.get("papers", [])
                if ppl:
                    f.write(f"**Grounded in**: {', '.join(ppl)}\n\n")
                if fi.get("count_evidence"):
                    f.write(f"**Evidence**: {esc(fi['count_evidence'])}\n\n")
                if fi.get("insight"):
                    f.write(f"{fi['insight']}\n\n")
                if fi.get("implication"):
                    f.write(f"**Why this matters**: {esc(fi['implication'])}\n\n")
            f.write("\n---\n\n")

        # --- Lineage summary (by category) ---
        if lineages:
            f.write("## Sub-Direction Lineage Summary\n\n")
            f.write("(detailed chains in `lineages/<category>.md`)\n\n")
            for cat, info in sorted(lineages.items()):
                f.write(f"### {cat} ({info.get('n_papers',0)} papers)\n\n")
                chains = info.get("chains", [])
                if not chains:
                    f.write("_No explicit evolution chains detected._\n\n")
                else:
                    f.write(f"**{len(chains)} chains detected.** Longest chain:\n\n")
                    longest = chains[0]
                    chain_str = " → ".join(
                        f"{c.get('date','?')} {c.get('title','')[:40]}"
                        for c in longest
                    )
                    f.write(f"  {chain_str}\n\n")
                frontier = info.get("frontier", [])
                if frontier:
                    f.write("**Frontier papers with admitted limitations:**\n\n")
                    for p in frontier[:3]:
                        f.write(f"- `{p.get('date','')}` {p.get('title','')}  \n")
                        f.write(f"  _limitation_: {esc(p.get('limitation',''))}\n")
                    f.write("\n")
            f.write("\n---\n\n")

        # --- Ideas (lineage-grounded) ---
        if ideas:
            f.write("## Lineage-Grounded Research Ideas\n\n")
            # Group by tier
            tiers = {}
            for idea in ideas:
                t = idea.get("tier", "A")
                tiers.setdefault(t, []).append(idea)

            tier_order = ["S", "A", "B", "C"]
            tier_desc = {
                "S": "S-tier — 1-2 months, zero baseline, high impact",
                "A": "A-tier — 3-6 months, flagship work",
                "B": "B-tier — longer term, thesis-level",
                "C": "C-tier — fill-in-the-blank quick wins",
            }

            for t in tier_order:
                if t not in tiers:
                    continue
                f.write(f"### {tier_desc[t]}\n\n")
                for i, idea in enumerate(tiers[t], 1):
                    f.write(f"#### 💎 {t}{i}: {esc(idea.get('title','(no title)'))}\n\n")
                    lineage = idea.get("lineage", {})
                    f.write(f"- **Lineage**: `{lineage.get('category','?')}` — "
                            f"Chain: {esc(lineage.get('chain_name','?'))}\n")
                    frontier = idea.get("frontier_paper", {})
                    f.write(f"- **Frontier paper**: {esc(frontier.get('title',''))} "
                            f"({esc(frontier.get('date',''))}, {esc(frontier.get('venue',''))})\n")
                    f.write(f"- **Admitted limitation**: *{esc(frontier.get('limitation',''))}*\n")
                    f.write(f"- **How this idea addresses it**: "
                            f"{esc(idea.get('addresses_limitation',''))}\n")
                    f.write(f"- **Why this is the logical next step**: "
                            f"{esc(idea.get('why_next_step',''))}\n")
                    f.write(f"- **Technical approach**: {esc(idea.get('technical_approach',''))}\n")
                    f.write(f"- **Benchmark**: {esc(idea.get('benchmark',''))}\n")
                    f.write(f"- **Baselines to beat**: {esc(idea.get('baselines',''))}\n")
                    f.write(f"- **Expected outcome**: {esc(idea.get('expected_outcome',''))}\n")
                    f.write(f"- **1-month milestone**: {esc(idea.get('one_month_milestone',''))}\n")
                    f.write(f"- **Target venue**: {esc(idea.get('target_venue',''))}\n\n")

            f.write("\n---\n\n")
            f.write("## Top Recommendations\n\n")
            # Auto-pick the top 3 S-tier ideas
            top = tiers.get("S", [])[:3]
            if top:
                for i, idea in enumerate(top, 1):
                    f.write(f"{i}. **{esc(idea.get('title',''))}** "
                            f"(lineage: {idea.get('lineage',{}).get('category','?')})\n")
                    f.write(f"   — {esc(idea.get('addresses_limitation',''))}\n\n")

    print(f"✓ Rendered: {out}")


if __name__ == "__main__":
    main()
