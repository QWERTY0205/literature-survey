#!/usr/bin/env python3
"""
ArXiv search helper. Does NOT replace using WebFetch from Claude — it's a reference
for how to construct queries.

ArXiv's search is keyword-based and low-recall. Issue 3+ differently-phrased queries
to maximize recall. Each query's URL is:

    https://arxiv.org/search/?searchtype=all&query=<URL_ENCODED_KEYWORDS>&start=0

Then use Claude's WebFetch tool to fetch each URL and extract:
  - arxiv_id
  - title
  - submission date
  - first author
  - one-sentence summary

Filter by date range (last 6 months by default) and write to <workspace>/arxiv_candidates.json
as [{"arxiv_id": "...", "title": "...", "date": "..."}].

## Example queries for different topics

### Streaming video understanding
- "streaming video LLM"
- "online video understanding"
- "real-time video LLM"
- "proactive video assistant"
- "full duplex video"

### Audio LLM reasoning
- "audio LLM reasoning"
- "speech reasoning"
- "audio chain-of-thought"
- "auditory reasoning"
- "SALMONN Qwen-Audio"

### Latent-space reasoning
- "latent chain-of-thought"
- "latent reasoning"
- "implicit reasoning tokens"
- "continuous thought"
- "diffusion reasoning"

### Full-duplex speech
- "full duplex speech"
- "duplex voice model"
- "turn taking dialogue"
- "streaming speech LLM"
- "Moshi voice agent"

---

## Why this is a reference, not a script

arXiv's HTML search page is dynamic and paginated. The reliable way to search is
via Claude's WebFetch with the URL pattern above, letting Claude parse the results.
You can issue 3-5 WebFetch calls in parallel (one per query), extract the unique
arxiv_ids, and then feed them to download_pdfs.py via arxiv_candidates.json.

This script exists to document the approach, not to replace Claude's role.
"""
print(__doc__)
