#!/usr/bin/env python3
"""
Build evolution lineage chains per category.

For each category in the merged results, this script:
1. Extracts papers sorted chronologically
2. Uses fuzzy matching to link each paper's `builds_on` entries to other papers
3. Constructs a DAG (nodes=papers, edges=builds_on)
4. Identifies "chains" (connected sub-paths) and "frontier" papers (latest with limitation)
5. Writes a per-category lineage markdown: <workspace>/lineages/<category>.md
6. Writes a unified lineages.json for downstream consumption

Usage:
    python3 build_lineages.py --workspace /data/paper/<topic>/
"""
import argparse
import json
import re
from pathlib import Path
from collections import defaultdict
from difflib import SequenceMatcher


def fuzzy_match_paper(target: str, candidates: list, threshold: float = 0.55) -> str:
    """Fuzzy match a builds_on string to a paper title or arxiv_id.
    Returns the best-match paper's title (or None if no match above threshold)."""
    if not target or not candidates:
        return None
    target_clean = re.sub(r"[^a-zA-Z0-9\s]", " ", target.lower())
    # Extract a short keyword for matching (first 4 tokens are usually enough)
    target_tokens = target_clean.split()[:6]
    target_key = " ".join(target_tokens)

    best_score = 0.0
    best = None
    for c in candidates:
        title = c.get("title", "")
        if not title:
            continue
        title_clean = re.sub(r"[^a-zA-Z0-9\s]", " ", title.lower())
        # Check if target's first significant word is in title
        score = SequenceMatcher(None, target_key, title_clean[: len(target_key) + 20]).ratio()
        # Boost: if target mentions an arxiv_id that matches
        if c.get("venue_or_arxiv", "") and c["venue_or_arxiv"].lower() in target.lower():
            score += 0.3
        # Boost: if first word of target matches a distinctive word in title
        first_word = target_tokens[0] if target_tokens else ""
        if first_word and len(first_word) >= 4 and first_word in title_clean:
            score += 0.15
        if score > best_score:
            best_score = score
            best = c
    if best_score >= threshold:
        return best["title"]
    return None


def parse_date(d: str) -> str:
    """Normalize date to YYYY-MM for sorting. Return '9999-99' if unparseable."""
    if not d:
        return "9999-99"
    m = re.match(r"(\d{4})[-/]?(\d{2})", str(d))
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return "9999-99"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    args = ap.parse_args()

    workspace = Path(args.workspace)
    merged_file = workspace / "all_merged.json"
    if not merged_file.exists():
        print(f"Missing {merged_file}. Run synthesize.py first.")
        return

    papers = json.load(open(merged_file))
    print(f"Loaded {len(papers)} papers")

    # Attach normalized date
    for p in papers:
        p["_date"] = parse_date(p.get("date", ""))

    # Group by category
    by_cat = defaultdict(list)
    for p in papers:
        by_cat[p.get("category", "other")].append(p)

    # Build lineages per category
    lineages_dir = workspace / "lineages"
    lineages_dir.mkdir(exist_ok=True)

    all_lineages = {}

    for cat, cat_papers in by_cat.items():
        cat_papers.sort(key=lambda p: p["_date"])
        if len(cat_papers) < 2:
            continue

        # For each paper, resolve builds_on to other papers in this category
        # (also allow cross-category matching later, but prioritize same-cat)
        edges = []  # (from_title, to_title) meaning "from builds on to"
        for p in cat_papers:
            for target in p.get("builds_on", []) or []:
                matched_title = fuzzy_match_paper(target, cat_papers)
                if not matched_title:
                    # Try cross-category
                    matched_title = fuzzy_match_paper(target, papers)
                if matched_title and matched_title != p["title"]:
                    edges.append((p["title"], matched_title))

        # Construct reverse adjacency: predecessor -> [successor]
        successors = defaultdict(list)
        predecessors = defaultdict(list)
        for succ_t, pred_t in edges:
            successors[pred_t].append(succ_t)
            predecessors[succ_t].append(pred_t)

        # Find frontier papers: latest papers with admitted limitation
        sorted_papers = sorted(cat_papers, key=lambda p: p["_date"], reverse=True)
        frontier = [p for p in sorted_papers[:5] if p.get("limitation")]

        # Find roots: no predecessors and have at least one successor
        roots = []
        for p in cat_papers:
            if p["title"] not in predecessors and successors.get(p["title"]):
                roots.append(p)

        # Build chains by BFS from each root, collecting longest paths
        def find_chains(start_title, visited=None):
            visited = visited or set()
            if start_title in visited:
                return []
            visited = visited | {start_title}
            succs = successors.get(start_title, [])
            if not succs:
                return [[start_title]]
            chains = []
            for s in succs:
                for sub in find_chains(s, visited):
                    chains.append([start_title] + sub)
            return chains

        all_chains = []
        for root in roots:
            all_chains.extend(find_chains(root["title"]))
        # Sort chains by length
        all_chains.sort(key=lambda c: -len(c))

        title_to_paper = {p["title"]: p for p in cat_papers}

        cat_lineage = {
            "category": cat,
            "n_papers": len(cat_papers),
            "chains": [],
            "frontier": [
                {
                    "title": p["title"],
                    "date": p.get("date", ""),
                    "venue": p.get("venue_or_arxiv", ""),
                    "limitation": p.get("limitation", ""),
                }
                for p in frontier
            ],
            "orphans": [  # papers with no edges
                p["title"] for p in cat_papers
                if p["title"] not in predecessors and p["title"] not in successors
            ],
        }
        for chain in all_chains[:10]:  # top 10 chains per category
            chain_info = []
            for t in chain:
                p = title_to_paper.get(t, {})
                chain_info.append({
                    "title": t,
                    "date": p.get("date", ""),
                    "venue": p.get("venue_or_arxiv", ""),
                    "method_summary": (p.get("method", "") or "")[:100],
                    "limitation": p.get("limitation", ""),
                })
            cat_lineage["chains"].append(chain_info)

        all_lineages[cat] = cat_lineage

        # Write per-category markdown
        md_path = lineages_dir / f"{cat}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# Lineage — {cat}\n\n")
            f.write(f"**{len(cat_papers)} papers** · **{len(all_chains)} chains detected**\n\n")
            f.write("---\n\n")

            if all_chains:
                f.write("## Evolution Chains\n\n")
                for idx, chain in enumerate(all_chains[:10], 1):
                    f.write(f"### Chain {idx}\n\n")
                    for i, t in enumerate(chain):
                        p = title_to_paper.get(t, {})
                        arrow = "" if i == 0 else "    ↓\n"
                        f.write(arrow)
                        f.write(f"**{p.get('date','?')}** · {t}  \n")
                        f.write(f"  · {p.get('method','')[:150]}\n")
                        lim = p.get('limitation')
                        if lim:
                            f.write(f"  · *admitted limitation*: {lim}\n")
                        f.write("\n")
                    f.write("\n")
            else:
                f.write("_No explicit builds_on edges detected. Falling back to chronological listing._\n\n")

            f.write("## Frontier Papers (latest with admitted limitation)\n\n")
            for p in frontier:
                f.write(f"- **{p.get('date','?')}** · {p['title']}\n")
                f.write(f"  · limitation: {p.get('limitation','')}\n")
                f.write(f"  · venue: {p.get('venue_or_arxiv','')}\n\n")

            if cat_lineage["orphans"]:
                f.write(f"## Orphans ({len(cat_lineage['orphans'])})\n\n")
                f.write("_Papers with no detected builds_on links in either direction._\n\n")
                for t in cat_lineage["orphans"][:20]:
                    f.write(f"- {t}\n")
                f.write("\n")

        print(f"  {cat}: {len(all_chains)} chains, {len(frontier)} frontier papers -> {md_path}")

    # Save unified lineages.json
    json.dump(all_lineages, open(workspace / "lineages.json", "w"),
              ensure_ascii=False, indent=2)
    print(f"\n✓ Unified lineages: {workspace / 'lineages.json'}")
    print(f"✓ Per-category lineages: {lineages_dir}/")
    print("\nNext: use these lineages to generate lineage-grounded ideas.")
    print("      Each idea should cite a specific chain + frontier paper + limitation.")


if __name__ == "__main__":
    main()
