# Synthesis Template (v2, lineage-grounded)

The synthesis phase produces two **structured JSON artifacts** (findings.json, ideas.json) which are then verified and rendered to the final markdown report. This separation is intentional — it prevents Claude from writing ungrounded prose.

**Do NOT write SYNTHESIS.md directly.** Write findings.json and ideas.json, run verify_synthesis.py, then run render_synthesis.py.

---

## Required inputs before synthesis starts

Make sure these files exist in the workspace:

- `all_merged.json` — structured paper data (from `synthesize.py`)
- `lineages.json` — per-category lineage DAGs (from `build_lineages.py`)
- `lineages/<category>.md` — human-readable lineage narratives
- `<TOPIC>_SURVEY.md` — categorized paper table (from `synthesize.py`)
- `<TOPIC>_FULL_TABLE.md` — flat table with problem/method classification

Start a **fresh Claude session** (via `claude --resume` from a clean CWD) loaded only with these files. This minimizes context pollution from the sub-agent run.

---

## Two-stage synthesis process

### Stage A — Findings only (no ideas yet)

Goal: produce `findings.json` with 8-15 cross-paper findings. **Do not write ideas in this stage.**

For each finding:

```json
{
  "id": "F1",
  "title": "Short declarative title",
  "papers": ["arxiv_id_1", "arxiv_id_2", "arxiv_id_3"],
  "count_evidence": "X of Y papers do Z",
  "insight": "What emerges only when you read these papers together — not something any single paper says. 1-2 sentences.",
  "implication": "Why this matters for research strategy"
}
```

**Hard rules** (enforced by verify_synthesis.py):
1. `papers` must have ≥ 2 arxiv_ids that exist in all_merged.json
2. `count_evidence` must be numerically consistent with the paper pool
3. `insight` must NOT contain generic phrases: "more research needed", "future work", "promising direction", "potential to", "should explore", "could benefit"
4. Each finding should cite papers across multiple categories when possible (cross-cutting findings are the most valuable)

**Good examples**:
- *"21 of 107 Audio RL papers use outcome reward; 0 use process reward — a systematic gap vs text LLM side (Math-Shepherd 2+ years old)"*
- *"Dual KV cache emerged simultaneously in 5 papers in 2026.03 (POINTS-Long, Think-While-Watching, TaYS, WAT, VST) without citing each other — suggests a common underlying problem: causal attention pollution in streaming VLMs"*
- *"PhoStream's Gemini 3 Pro result (16.4% Forward) plus StreamReady's RDY token plus AURA's Silent-Speech loss all target the same 'early response bias' phenomenon — none of them actually solve it, they just measure or mitigate"*

**Bad examples** (will be rejected):
- "Many papers use transformers" (generic)
- "RL is becoming popular" (no count)
- "Research should focus on efficiency" (hedging + motherhood)

### Stage B — Lineage-grounded ideas

Goal: produce `ideas.json` with 10-40 ideas, each tied to a specific lineage chain.

**Hard rules** (every idea must have all these fields):

```json
{
  "id": "S1",
  "title": "Concrete title with specific technique name",
  "tier": "S/A/B/C",

  "lineage": {
    "category": "must exist in lineages.json",
    "chain_name": "human-readable chain name from build_lineages output"
  },

  "frontier_paper": {
    "title": "Must match a paper in all_merged.json",
    "arxiv_id": "2602.15329",
    "date": "2026-02",
    "venue": "arxiv/NeurIPS 2025/etc",
    "limitation": "Copy the limitation field from all_merged.json — this is the 'next step anchor'"
  },

  "addresses_limitation": "One sentence: how this idea specifically solves that limitation",
  "why_next_step": "One paragraph: why this is the physical next step on this chain — reference the prior step and explain the gradient of improvement",

  "technical_approach": "≥100 chars: architecture, training strategy, data. Enough detail to start coding.",
  "differentiation": "How this differs from the frontier_paper's approach",

  "benchmark": "Specific benchmark name with current SOTA number",
  "baselines": "Papers you'll beat",
  "expected_outcome": "Specific metric target: '+X% on benchmark Y'",

  "one_month_milestone": "First verifiable milestone in 1 month",
  "target_venue": "CVPR/ICCV/NeurIPS/ICLR/ACL",
  "why_now": "Why this window exists (which enabling papers/tools just came out)"
}
```

**Hard rules** (enforced by verify_synthesis.py):
1. `lineage.category` must exist in `lineages.json`
2. `frontier_paper.title` must fuzzy-match a paper in `all_merged.json`
3. `frontier_paper.limitation` must be non-empty (copied from the paper's own limitation field)
4. `addresses_limitation` must explicitly reference the limitation text
5. `technical_approach` must be ≥100 characters
6. `benchmark` and `one_month_milestone` must be non-empty

**See `references/lineage_example.md` for a complete worked example.**

---

## Tier assignment guide

- **S** — 1-2 months to first paper, zero current baseline, high impact
- **A** — 3-6 months, flagship-level work, 2-4 comparable baselines
- **B** — 6-12 months, thesis-level, needs significant infra
- **C** — 1-2 weeks fill-in-the-blank quick wins

---

## After writing findings.json and ideas.json

```bash
# 1. Verify (will fail loudly on issues)
python3 scripts/verify_synthesis.py --workspace /data/paper/<topic>/

# 2. If passed, render the final markdown
python3 scripts/render_synthesis.py --workspace /data/paper/<topic>/ --topic "<TOPIC>"
```

The final `<TOPIC>_SYNTHESIS.md` is deterministically generated from the verified JSONs. No free-form writing at this stage.

---

## Why this process produces better ideas

1. **Lineage forces causal chain thinking**: Not "find a gap" but "extend an existing chain one step"
2. **Frontier limitation comes from the paper itself**: No Claude-hallucinated gaps
3. **Verification catches both false citations and generic hedging**: Machine-checked quality floor
4. **Fresh context synthesis**: No sub-agent transcript pollution in the reasoning context
5. **Mechanical rendering**: The markdown cannot introduce ungrounded content — it only formats the verified JSON

This is strictly stronger than "read all papers and write ideas" because every constraint is checkable.
