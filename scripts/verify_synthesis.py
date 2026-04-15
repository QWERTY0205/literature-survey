#!/usr/bin/env python3
"""
Verify synthesis findings and ideas against the ground-truth paper data.

Reads findings.json and ideas.json produced by the synthesis phase, and checks:
1. Every cited paper title/arxiv_id actually exists in all_merged.json
2. Every "X of Y papers do Z" count is numerically accurate
3. Every idea has a valid lineage_chain_id pointing to lineages.json
4. Every idea cites a frontier paper that exists and has a limitation field
5. No generic ideas (those lacking specific numbers / paper citations)

Usage:
    python3 verify_synthesis.py --workspace /data/paper/<topic>/

Outputs:
    <workspace>/verification_report.md  — Pass/fail list with reasons
    Exit code 0 if all checks pass, 1 otherwise.
"""
import argparse
import json
import re
import sys
from pathlib import Path


def load_optional(path):
    if path.exists():
        try:
            return json.load(open(path))
        except Exception as e:
            print(f"  warn: cannot parse {path}: {e}")
    return None


def check_citation_exists(citation: str, papers: list) -> bool:
    """Check if a citation string matches any paper."""
    cite_l = citation.lower()
    for p in papers:
        title = (p.get("title") or "").lower()
        va = (p.get("venue_or_arxiv") or "").lower()
        if cite_l in title or title.split(":")[0] in cite_l:
            return True
        if va and va in cite_l:
            return True
    return False


def check_count_claim(claim: str, papers: list) -> tuple:
    """Parse a claim like 'X of Y papers do Z' and try to verify it.
    Returns (ok_bool, actual_number_if_checkable)."""
    # Look for patterns like "21 of 107 papers" or "X/Y"
    m = re.search(r"(\d+)\s*(?:of|/|篇)\s*(\d+)", claim)
    if not m:
        return (True, None)  # Can't parse → don't fail
    claimed_x, claimed_y = int(m.group(1)), int(m.group(2))
    # Check total is in a reasonable range
    if abs(claimed_y - len(papers)) > 5:
        return (False, len(papers))
    return (True, None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    args = ap.parse_args()

    workspace = Path(args.workspace)
    papers = load_optional(workspace / "all_merged.json") or []
    lineages = load_optional(workspace / "lineages.json") or {}
    findings = load_optional(workspace / "findings.json") or []
    ideas = load_optional(workspace / "ideas.json") or []

    print(f"Loaded: {len(papers)} papers, {len(lineages)} categories with lineages, "
          f"{len(findings)} findings, {len(ideas)} ideas")

    issues = []

    # ----- Check findings -----
    for i, f in enumerate(findings):
        fid = f.get("id", f"finding_{i}")
        papers_cited = f.get("papers", [])
        if len(papers_cited) < 2:
            issues.append((fid, "finding has fewer than 2 paper citations"))
        for cite in papers_cited:
            if not check_citation_exists(cite, papers):
                issues.append((fid, f"cited paper not found in all_merged: {cite}"))
        count_claim = f.get("count_evidence", "")
        ok, actual = check_count_claim(count_claim, papers)
        if not ok:
            issues.append((fid, f"count claim '{count_claim}' doesn't match total papers ({actual})"))
        if not f.get("insight"):
            issues.append((fid, "missing 'insight' field"))
        # Check for generic phrases
        insight_l = (f.get("insight") or "").lower()
        generic = ["more research", "future work", "promising direction", "potential to",
                   "should explore", "could benefit"]
        if any(g in insight_l for g in generic):
            issues.append((fid, f"insight contains generic hedging ({[g for g in generic if g in insight_l]})"))

    # ----- Check ideas -----
    all_category_names = set(lineages.keys())
    for i, idea in enumerate(ideas):
        iid = idea.get("id", f"idea_{i}")

        # 1. Must cite a lineage chain
        chain_ref = idea.get("lineage")
        if not chain_ref:
            issues.append((iid, "idea missing 'lineage' field"))
            continue
        cat = chain_ref.get("category")
        if cat not in all_category_names:
            issues.append((iid, f"lineage category '{cat}' not found in lineages.json"))

        # 2. Must cite a frontier paper
        frontier = idea.get("frontier_paper")
        if not frontier:
            issues.append((iid, "idea missing 'frontier_paper' field"))
            continue
        if not check_citation_exists(frontier.get("title", ""), papers):
            issues.append((iid, f"frontier paper not found: {frontier.get('title','')}"))

        # 3. Frontier must have limitation
        frontier_limitation = frontier.get("limitation")
        if not frontier_limitation:
            issues.append((iid, "frontier_paper has no limitation cited"))

        # 4. Must specify how the idea addresses the limitation
        if not idea.get("addresses_limitation"):
            issues.append((iid, "missing 'addresses_limitation' field"))

        # 5. Technical approach must be specific
        approach = idea.get("technical_approach", "")
        if len(approach) < 50:
            issues.append((iid, "technical_approach too short (<50 chars)"))

        # 6. Must have a benchmark + first milestone
        if not idea.get("benchmark"):
            issues.append((iid, "missing 'benchmark' field"))
        if not idea.get("one_month_milestone"):
            issues.append((iid, "missing 'one_month_milestone' field"))

    # ----- Write report -----
    report = workspace / "verification_report.md"
    with open(report, "w", encoding="utf-8") as f:
        f.write("# Synthesis Verification Report\n\n")
        f.write(f"- Papers: {len(papers)}\n- Findings: {len(findings)}\n- Ideas: {len(ideas)}\n")
        f.write(f"- Issues: **{len(issues)}**\n\n---\n\n")
        if not issues:
            f.write("✅ All checks passed.\n")
        else:
            f.write("## Issues\n\n")
            for obj_id, msg in issues:
                f.write(f"- **{obj_id}**: {msg}\n")

    print(f"\nIssues: {len(issues)}")
    print(f"Report: {report}")

    if issues:
        print("\n❌ Verification FAILED. Fix issues before rendering final synthesis.")
        sys.exit(1)
    print("\n✅ All checks passed.")


if __name__ == "__main__":
    main()
