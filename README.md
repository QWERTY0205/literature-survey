# Literature Survey — Claude Code Skill

**Deep, citation-grounded research surveys — full PDFs, lineage tracing, and verified research ideas — in one command.**

A Claude Code skill that automates the entire pipeline of a top-tier literature survey:

1. Search top conferences + arXiv in parallel
2. Download and extract full PDF text for every candidate paper
3. Have parallel sub-agents read each paper and produce structured analysis (with `builds_on` + `limitation` extraction)
4. Auto-construct **per-category evolution DAGs** showing which papers build on which
5. Generate **lineage-grounded research ideas** that are anchored to specific papers' admitted limitations
6. Mechanically verify every citation and count claim before producing the final report

Unlike "summarize some papers"-style tools, this skill produces a **falsifiable** synthesis: every finding and idea is pinned to specific paper IDs, numeric counts are machine-checked, and ideas must reference a frontier paper's own admitted limitation — not a Claude-hallucinated gap.

---

## What you get

For each survey run, the skill produces:

| Output | Purpose |
|--------|---------|
| `<TOPIC>_SURVEY.md` | Categorized paper table grouped per sub-direction |
| `<TOPIC>_FULL_TABLE.md` | Flat table of all papers with auto-classified `problem_type` / `method_type` — spreadsheet-friendly |
| `<TOPIC>_SYNTHESIS.md` | Cross-paper findings + lineage-grounded research ideas |
| `lineages/<category>.md` | Per-category evolution chains: which paper built on which, and what's the current frontier |
| `all_merged.json` | Structured data for every analyzed paper |
| `lineages.json` | DAG data (category → chains → frontier papers) |
| `findings.json` / `ideas.json` | Verified structured synthesis (source of truth for the final markdown) |

---

## Why this is stronger than typical literature surveys

Most AI-assisted surveys collapse into "read abstracts → write generic ideas". This skill instead:

- **Reads full PDF text** (pdftotext layout mode, all pages), not abstracts
- **Extracts `builds_on` and `limitation`** per paper from `related work` and `conclusion` sections
- **Builds evolution DAGs** per category — so ideas come from "extend chain X one step" rather than "find a gap"
- **Separates synthesis into typed JSON stages** (findings.json → ideas.json) so context pollution doesn't degrade idea quality
- **Machine-verifies** every citation, count claim, and lineage reference before rendering the final report
- **Rejects generic hedging** ("more research is needed", "could benefit from") at the verification layer

See `references/lineage_example.md` for a complete worked example.

---

## Installation

### Option A: drop-in (recommended)

```bash
cd ~/.claude/skills
git clone https://github.com/<YOUR_USERNAME>/literature-survey.git
```

Then in any Claude Code session, the skill will be available automatically. Trigger it by saying "调研 X" / "survey X" / "review X" / "X 领域有什么新工作".

### Option B: manual copy

Copy the entire `literature-survey/` directory to `~/.claude/skills/literature-survey/` (or to any project's `.claude/skills/` for project-scoped use).

### Prerequisites

The skill sets these up automatically on first run, but you can pre-install:

```bash
# PDF text extraction
apt-get install -y poppler-utils

# Conference search (papers.cool scraper)
git clone https://github.com/QWERTY0205/papers-cool-downloader /tmp/papers-cool-downloader
pip install requests
```

---

## Usage

Just ask Claude:

```
调研一下全双工语音模型最近的研究
```

Claude will:
1. Confirm scope with you (topic, venues, keywords, date range)
2. Set up `/data/paper/<topic>/` workspace
3. Run the 10-phase pipeline (see `SKILL.md`)
4. Produce the 4 report files in the workspace

**Expected wall-clock**: 1–2 hours for a 100–200 paper survey. Most of the time is sub-agent wait time; main-context work is <15 minutes.

### Manual per-phase commands

If you want to run phases individually:

```bash
WS=/data/paper/<topic>
TOPIC="<TOPIC NAME>"

# Phase 1: workspace setup (auto permissions)
bash scripts/setup_permissions.sh "$WS"

# Phase 2-3: search
python3 scripts/search_conferences.py --workspace "$WS" \
  --keywords "keyword 1" "keyword 2" \
  --venues CVPR.2025 ICCV.2025 NeurIPS.2025 ICLR.2026

# (Phase 3 arxiv search is done via Claude's WebFetch inline — no script)

# Phase 4: download PDFs
python3 scripts/download_pdfs.py --workspace "$WS" --mode both

# Phase 5: extract text
python3 scripts/extract_text.py --workspace "$WS"

# Phase 6: batch (and then launch analysis sub-agents via Claude)
python3 scripts/create_batches.py --workspace "$WS" --batch-size 3

# Phase 7: merge + tables
python3 scripts/synthesize.py      --workspace "$WS" --topic "$TOPIC"
python3 scripts/generate_table.py  --workspace "$WS" --topic "$TOPIC"

# Phase 7.5: lineages
python3 scripts/build_lineages.py  --workspace "$WS"

# Phase 8 (synthesis — requires Claude interaction for findings/ideas JSON)
# Then:
python3 scripts/verify_synthesis.py  --workspace "$WS"
python3 scripts/render_synthesis.py  --workspace "$WS" --topic "$TOPIC"
```

---

## Repository structure

```
literature-survey/
├── SKILL.md                           # Main skill doc (triggered by Claude)
├── README.md                          # This file
├── LICENSE                            # MIT
├── scripts/
│   ├── setup_permissions.sh           # Workspace permissions
│   ├── search_conferences.py          # papers.cool scraper wrapper
│   ├── search_arxiv.py                # arXiv query helper (reference)
│   ├── download_pdfs.py               # Multi-threaded downloader
│   ├── extract_text.py                # pdftotext + manifest builder
│   ├── create_batches.py              # Split papers into size-3 batches
│   ├── synthesize.py                  # Merge → categorized SURVEY.md
│   ├── generate_table.py              # Flat FULL_TABLE.md with type tags
│   ├── build_lineages.py              # Evolution DAGs per category
│   ├── verify_synthesis.py            # Validate findings/ideas JSON
│   ├── render_synthesis.py            # Render SYNTHESIS.md from verified JSON
│   └── agent_prompt_template.md       # Sub-agent prompt (with builds_on/limitation)
└── references/
    ├── synthesis_template.md          # Required findings/ideas JSON schema
    └── lineage_example.md             # Good vs bad idea examples
```

---

## Design notes

### The "lineage-grounded idea" constraint

The defining difference vs a typical survey is the **hard rule** that every research idea must contain:

- `lineage.category` + `chain_name` (must exist in `lineages.json`)
- `frontier_paper.title` + `limitation` (must match a real paper's own admitted limitation)
- `addresses_limitation` (how the idea specifically resolves that limitation)
- `why_next_step` (why this is the physical next step on the chain)

`verify_synthesis.py` rejects any idea missing these or using generic hedging. This makes ideas **falsifiable** — the reader can check: is this really a gap? Does the frontier paper really admit it?

### Common pitfalls this skill handles

- Sub-agent PDF rendering fails → skill falls back to pdftotext text files
- Batch size too large → skill fixes at 3 papers/batch
- Title/txt_path mismatches in batch JSONs → sub-agents instructed to trust file content
- Usage Policy errors on safety-related papers → retry in English, smaller chunks
- arXiv single-query low recall → issue 3+ different phrasings
- Generic "more research needed" ideas → verifier rejects them at lint time

---

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgements

- [papers-cool-downloader](https://github.com/QWERTY0205/papers-cool-downloader) for the papers.cool scraping backend
- [papers.cool](https://papers.cool) for the unified conference search interface

## Contributing

Issues and PRs welcome. If you run this on a new research area and find edge cases (weird category structures, lineage extraction failures, verification false positives), please open an issue with the workspace state attached.
