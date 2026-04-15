---
name: literature-survey
description: Conduct a deep literature survey across top conferences and arXiv preprints. Use when the user asks to 调研/survey/review a research direction, compile papers on a topic, analyze trends in a field, or find research gaps and ideas. Produces categorized paper tables, trend analysis, and actionable research ideas based on full-PDF deep reading of dozens to hundreds of papers.
---

# Literature Survey Skill

End-to-end pipeline for producing a deep, citation-grounded survey on a research topic. Every paper is downloaded as PDF, converted to full text, and read by a sub-agent to extract structured fields — not just abstracts.

This is **NOT** a lightweight "list some papers" task. It produces:
- A categorized table of 50–400 papers
- Per-paper structured analysis (problem/method/novelty/category/training-strategy/benchmark/key-number/open-source)
- Trend analysis, research gaps, and actionable research ideas grounded in the full-text reading

---

## When to trigger

- User asks to **调研 / survey / review** a research direction
- User asks to **compile / analyze papers** on a topic
- User asks **"what is hot in X"** or **"what are research gaps in X"**
- User asks for **research ideas** in a specific field
- User mentions wanting to cover **顶会论文 + arxiv**

Typical phrases: "调研一下…", "帮我看看…领域在做什么", "给我想几个 idea about …", "最近 X 方向有什么新工作"

---

## Prerequisites (one-time setup)

```bash
# 1. Clone papers-cool-downloader (for conference search via papers.cool)
git clone https://github.com/QWERTY0205/papers-cool-downloader /tmp/papers-cool-downloader
pip install requests

# 2. Install poppler-utils (for PDF text extraction via pdftotext)
apt-get install -y poppler-utils

# 3. Grant permissions in the workspace directory
#    See the `scripts/setup_permissions.sh` helper
```

---

## Workflow (10 phases, lineage-aware)

Follow these phases in order. Each phase has a dedicated helper script under `scripts/`.

**Key design principle**: The synthesis phase is **split from paper analysis** via structured JSON artifacts (lineages.json → findings.json → ideas.json → markdown). This prevents the context pollution that plagues "read all papers and freeform write ideas" workflows.

### Phase 1: SCOPE & SETUP

1. **Confirm the research topic** with the user in one sentence. Be specific: "流式视频理解" is good; "视频" is too broad.
2. **Pick a workspace directory** under `/data/paper/<topic_slug>/`. Create subdirs:
   ```
   /data/paper/<topic_slug>/
     ├── scripts/
     ├── pdfs/       (arxiv PDFs)
     ├── pdfs_conf/  (conference PDFs)
     ├── texts/      (pdftotext output for arxiv)
     ├── texts_conf/ (pdftotext output for conferences)
     ├── batches/    (sub-agent input batches)
     ├── results/    (sub-agent output per batch)
     └── analysis/
   ```
3. **Define scope**: which conferences (default: CVPR 2025, ICCV 2025, NeurIPS 2025, ICML 2025, ACL 2025, ICLR 2026, AAAI 2026), what arXiv date range (default: last 6 months).
4. **Generate keyword list**: Use 10–20 keywords from the topic. Include synonyms, variations, common abbreviations.

### Phase 2: SEARCH CONFERENCES

Use `papers-cool-downloader` to search each venue in parallel. See `scripts/search_conferences.py`.

```bash
# Runs papers-cool-downloader for each venue in parallel.
# Output: /data/paper/<topic>/<venue_tag>_raw.json per venue.
python3 scripts/search_conferences.py \
  --workspace /data/paper/<topic>/ \
  --keywords "streaming video" "video LLM" "online video" \
  --venues CVPR.2025 ICCV.2025 NeurIPS.2025 ICLR.2026 AAAI.2026 ACL.2025 ICML.2025
```

### Phase 3: SEARCH ARXIV

Use `WebFetch` on `arxiv.org/search/` with multiple keyword queries (at least 3–5 different phrasings). **Important**: arXiv search only shows ~50 papers per query — use multiple phrasings to maximize coverage.

For each query, extract papers with submission date in the target range (usually last 6 months). Save to `arxiv_candidates.json`.

Typical queries:
```
https://arxiv.org/search/?searchtype=all&query=<KEYWORD>&start=0
```

**Always issue 3+ different keyword queries** — single-query recall is poor.

### Phase 4: DOWNLOAD PDFs

Use the helper script `scripts/download_pdfs.py`:
- **ArXiv**: direct URL `https://arxiv.org/pdf/<arxiv_id>`
- **Conferences**: use the `pdf_url` field already parsed by papers-cool-downloader
- 8–10 threads, skip existing files, retry failures 3×

```bash
python3 scripts/download_pdfs.py --workspace /data/paper/<topic>/
```

### Phase 5: EXTRACT TEXT

Convert every PDF to text using `pdftotext -layout`. Full pages, not just first 5. See `scripts/extract_text.py`.

```bash
python3 scripts/extract_text.py --workspace /data/paper/<topic>/
```

Output files are at `texts/<basename>.txt` and `texts_conf/<basename>.txt`.

### Phase 6: BATCH & ANALYZE (parallel sub-agents)

Split papers into batches of **3 per batch** (important — larger batches exceed sub-agent context). See `scripts/create_batches.py`.

Then **launch 5–10 parallel sub-agents**, each handling 5–6 batches (15–18 papers). Each sub-agent reads the full text of each paper and produces structured analysis.

**Critical constraints** (from hard-learned experience):
- **Batch size = 3 papers**. Larger fails with "Request too large (max 32MB)".
- **Sub-agents must Read the `txt_path` field**, not PDF directly (PDF rendering often fails in sub-agent sandbox due to missing poppler-utils).
- **batch JSON files often have title↔txt_path mismatches** — instruct sub-agents to use `txt_path` content as source of truth.
- **Some batches may fail with Usage Policy errors** due to "safety" or "adversarial" keywords in the papers. Retry with smaller chunks (1 batch per agent) and use more academic/objective language in the prompt.

See `scripts/launch_analysis_agents.py` for the exact prompt template.

### Phase 7: MERGE & GENERATE TABLE

**两个表都要生成**（它们互补）：

1. **Categorized Survey** (`scripts/synthesize.py`) — 按类别分组的导航表
   - Merge all `results/b_*.json` files
   - Deduplicate by title
   - Compute category/training/venue distributions
   - Generate `<TOPIC>_SURVEY.md` with papers grouped per category

2. **Full Flat Table** (`scripts/generate_table.py`) — 完整扁平大表（推荐，便于飞书/Excel 使用）
   - Auto-classify each paper into problem_type + method_type using keyword rules
   - Generate `<TOPIC>_FULL_TABLE.md` with all papers in one sortable table
   - Includes extra columns: problem_type, method_type, benchmark, training, key_number
   - Shows problem type and method type distributions for trend spotting

```bash
python3 scripts/synthesize.py --workspace /data/paper/<topic>/ --topic "<TOPIC>"
python3 scripts/generate_table.py --workspace /data/paper/<topic>/ --topic "<TOPIC>"
```

### Phase 7.5: BUILD LINEAGES 🆕

For each sub-direction (category), trace the evolution chains: which papers build on which, and what's the "frontier" each chain has reached.

```bash
python3 scripts/build_lineages.py --workspace /data/paper/<topic>/
```

**Requirements**: Sub-agents in Phase 6 must have extracted `builds_on` and `limitation` fields per paper (see `scripts/agent_prompt_template.md` v2).

**Output**:
- `lineages.json` — unified DAG data
- `lineages/<category>.md` — per-category human-readable chain narratives like:
  ```
  2024.06 MA-LMM — dense memory bank
     ↓ [improves]
  2024.12 Flash-VStream — sparse memory
     ↓ [improves]
  2025.10 EventMemAgent — event graph + agentic RL ← FRONTIER
     admitted limitation: "LLM hallucinates event boundaries"
  ```

This transforms synthesis from "find gaps" into "extend specific chains" — producing far better ideas.

### Phase 8: LINEAGE-GROUNDED SYNTHESIS 🆕

**Split into 4 substeps** to prevent context pollution and generic idea drift. **Start a fresh Claude session** for Phase 8a onward — `claude --resume` from a clean CWD, or begin a new conversation loaded only with `all_merged.json` + `lineages.json`.

#### Phase 8a: Write `findings.json` (cross-paper findings ONLY, no ideas yet)

In the fresh session, Claude writes 8-15 findings to `findings.json`. Each finding:
- Cites ≥2 papers (arxiv_ids that exist in all_merged.json)
- Has a numeric count claim ("X of Y papers do Z")
- States a cross-paper insight (not something any single paper says)
- NO generic hedging ("more research needed" → rejected)

See `references/synthesis_template.md` for the exact JSON schema and `references/lineage_example.md` for good/bad examples.

#### Phase 8b: Write `ideas.json` (lineage-grounded ideas ONLY)

In a fresh turn (ideally after `/clear` or new session), Claude reads:
- `findings.json` (from 8a)
- `lineages.json` / `lineages/<category>.md`
- `all_merged.json` (for limitation lookup)

And writes 10-40 ideas, **each tied to a specific chain in lineages.json**. Required fields per idea:
- `lineage.category` + `chain_name`
- `frontier_paper.title` + `limitation` (copied from all_merged.json)
- `addresses_limitation` (how this idea solves that specific limitation)
- `why_next_step` (why this is the physical next step on the chain)
- `technical_approach` (≥100 chars)
- `benchmark` + `one_month_milestone`

**Hard rule**: an idea that doesn't reference a frontier paper's admitted limitation is rejected.

#### Phase 8c: Verify

```bash
python3 scripts/verify_synthesis.py --workspace /data/paper/<topic>/
```

This script checks:
- Every cited paper exists in `all_merged.json`
- Every "X of Y" count is numerically consistent
- Every idea has a valid lineage → frontier → limitation chain
- No generic hedging phrases in findings
- All required fields are present and non-trivial

**Exit 0 → proceed. Exit 1 → fix findings.json / ideas.json and retry.**

#### Phase 8d: Render

```bash
python3 scripts/render_synthesis.py --workspace /data/paper/<topic>/ --topic "<TOPIC>"
```

Mechanically produces `<TOPIC>_SYNTHESIS.md` from the verified JSON. **This is the only legitimate way to produce the synthesis markdown** — don't write it freehand.

See `references/synthesis_template.md` and `references/lineage_example.md` for the full workflow.

---

## Quality bar

A survey is **only finished** when:
- [ ] ≥ 50 papers analyzed (ideally 100–300)
- [ ] Every paper's `method` field has technical detail from the method section, not just abstract
- [ ] Every paper has `key_number` — at least one concrete experimental result
- [ ] Dedup is done (same paper under different titles merged)
- [ ] At least 8 categories identified with clear definitions
- [ ] Synthesis includes at least 5 "cross-paper insights" (things you only see when reading multiple papers together)
- [ ] At least 10 research ideas, each with motivation + technical approach + venue estimate

---

## Common pitfalls (learned from experience)

1. **Don't rely on abstracts** — sub-agents will happily use the abstract if you don't insist on `txt_path`. The whole value of this skill is in full-PDF reading.

2. **Batch = 3, not 5 or 10** — PDFs are big. 5 papers often fails, 10 always fails.

3. **Conference PDFs fail more than arxiv PDFs** — openreview/aaai sites rate-limit or block. Multi-thread helps but you'll still lose 10–30%.

4. **Title mismatch in batch JSON** — papers-cool-downloader's output sometimes has shifted title/pdf_url fields. Tell sub-agents to trust txt_path content.

5. **Usage Policy errors** — adversarial/safety/attack/deepfake keywords in papers trigger filter. Split into single-batch agents and use academic language in the prompt.

6. **arXiv search recall is poor** — issue 3+ differently-phrased queries to maximize coverage. Don't trust a single search.

7. **PDF extraction limit** — by default pdftotext extracts all pages, which is what you want (NOT `-f 1 -l 5` — that loses method/experiments sections).

8. **Sub-agent permissions** — sub-agents have a restricted sandbox. Make sure global settings.json has `"Read"`, `"Write"`, `additionalDirectories` covering your workspace. See `scripts/setup_permissions.sh`.

---

## Output files produced

| File | Description |
|------|-------------|
| `<TOPIC>_SURVEY.md` | Categorized paper table, grouped per category (navigation-friendly) |
| `<TOPIC>_FULL_TABLE.md` | Flat table of all papers with auto-classified problem_type + method_type; best for spreadsheet/Feishu import |
| `<TOPIC>_SYNTHESIS.md` | Deep insights + lineage-grounded research ideas (rendered from verified JSON) |
| `lineages/<category>.md` | 🆕 Per-category evolution chain narratives (which paper built on which) |
| `lineages.json` | 🆕 Unified DAG data (category → chains → frontier papers) |
| `findings.json` | 🆕 Structured cross-paper findings (Stage 8a output, verified) |
| `ideas.json` | 🆕 Structured lineage-grounded ideas (Stage 8b output, verified) |
| `verification_report.md` | 🆕 Output of verify_synthesis.py |
| `all_merged.json` | Structured data for all analyzed papers |
| `manifest.json` | arXiv papers with pdf_path + txt_path |
| `confs_manifest.json` | Conference papers with pdf_path + txt_path |
| `results/b_*.json` | Per-batch sub-agent outputs (source of truth) |

---

## Reference scripts

All helper scripts are in `scripts/`. See their headers for usage details.

- `setup_permissions.sh` — Grant the workspace the needed permissions
- `search_conferences.py` — papers-cool-downloader wrapper
- `search_arxiv.py` — arXiv multi-query helper (reference doc)
- `download_pdfs.py` — Multi-threaded PDF downloader with dedup
- `extract_text.py` — Batch pdftotext runner + manifest generator
- `create_batches.py` — Split manifest into size-3 batches
- `agent_prompt_template.md` — Sub-agent prompt (v2, includes `builds_on` and `limitation` extraction)
- `synthesize.py` — Merge results and generate categorized `_SURVEY.md` + `all_merged.json`
- `generate_table.py` — Generate flat `_FULL_TABLE.md` with problem/method type classification
- `build_lineages.py` 🆕 — Build per-category evolution DAGs from `builds_on` fields
- `verify_synthesis.py` 🆕 — Validate findings.json / ideas.json against ground truth
- `render_synthesis.py` 🆕 — Mechanically render final `_SYNTHESIS.md` from verified JSON

---

## Example invocation

```
User: 帮我调研一下全双工语音模型最近的研究
You (invoking this skill):
  - Topic: 全双工语音模型 / full-duplex speech model
  - Workspace: /data/paper/full_duplex_speech/
  - Keywords: "full duplex speech", "duplex voice", "speech LLM", "spoken dialogue system", "turn-taking", "Moshi", "LLaMA-Omni", "real-time voice agent", "streaming speech"
  - Venues: CVPR 2025, ICCV 2025, NeurIPS 2025, ICLR 2026, AAAI 2026, ACL 2025, ICML 2025, INTERSPEECH 2025
  - arXiv date range: 2025-10 to 2026-04
  
  Then run all 8 phases.
```

**Expected time**: 1–2 hours of wall-clock for a 100–200 paper survey (mostly sub-agent wait time; main-context work is <15 minutes).
