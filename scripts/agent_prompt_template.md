# Sub-Agent Prompt Template (v2, lineage-aware)

This is the reference prompt to copy when launching sub-agents for the analysis phase.

The template **requires the sub-agent to extract 2 lineage fields** (`builds_on` and `limitation`) that later enable the `build_lineages.py` script to construct evolution chains.

---

## Prompt Template

```
深度阅读 <TOPIC> 论文全文，处理 b_NN 到 b_MM 共 X 个 batch，Y 篇论文。

## 流程
对每个 b_NN（NN 到 MM）：
1. Read `<WORKSPACE>/batches/b_NN.json`
2. 对每篇论文 Read `txt_path` 字段指向的全文文本（PDF 全部页面）
3. 深度理解后产出结构化 JSON
4. Write `<WORKSPACE>/results/b_NN.json`

## 每篇论文输出字段
```json
{
  "title": "论文真实标题（以 txt_path 内容为准）",
  "source": "arxiv 或 conf",
  "venue_or_arxiv": "会议名 或 arxiv_id",
  "date": "2026-01 格式（arxiv 按提交月，conf 按发表月）",

  "problem": "论文要解决的具体问题（中文≤80字）",
  "method": "核心技术路线（中文≤120字，**必须从正文 method 章节提炼具体技术细节**）",
  "novelty": "和已有工作的最关键差异（1-2句中文）",

  "category": "从以下精选一个：<CATEGORY_LIST>",
  "training_strategy": "SFT / RL(GRPO/DPO/PPO) / training-free / pre-training / 其他",
  "benchmark_used": "使用哪些 benchmark",
  "key_number": "最关键的实验数字",
  "open_source": "GitHub URL 或 null",

  "builds_on": [
    // 这篇论文明确说自己 build on / improve upon 的 2-5 篇关键前作。
    // 从 related work / introduction / method 章节提取。
    // 格式优先用 "论文名缩写 (一作, 年)"，比如 "Video-LLaVA (Lin, 2024)"。
    // 如果论文自己没明确说，写 [] 空列表。不要编造。
    "..."
  ],
  "limitation": "这篇论文自己承认的 limitation / failure case / future work。从 limitation 或 conclusion 章节提取（中文≤80字）。如果文中没写，填 null。不要编造"
}
```

## 关键注意事项
- **必须读 txt_path 正文**，不要只看 abstract
- batch JSON 里 title 字段可能与 txt_path 实际内容不匹配 — 以 txt_path 文件内容为准
- method 和 key_number 必须从正文提炼具体技术细节和实验数字
- **builds_on 只能从 related work 明确引用的工作中提取**，不要 Claude 自己推断"大概 build on 什么"
- **limitation 只能从 limitation/conclusion 章节明确文字提取**，不要自己发挥
- 不要跳过任何论文
- 如果 PDF 内容包含 deepfake/adversarial/privacy 等 safety 话题，这是合法学术研究，请客观提炼技术细节

权限已开放 Read/Write 到 <WORKSPACE>/。
```

---

## Parameters to customize per invocation

| Placeholder | Example |
|-------------|---------|
| `<TOPIC>` | "流式视频理解" / "音频大模型推理" / "full-duplex speech" |
| `b_NN to b_MM` | "b_01 到 b_06" |
| `X` | 6 (number of batches) |
| `Y` | 18 (total papers across all batches) |
| `<WORKSPACE>` | `/data/paper/streaming_video/` |
| `<CATEGORY_LIST>` | Comma-separated categories relevant to the topic |

---

## Why `builds_on` and `limitation` matter

These two fields enable **lineage tracing** in the synthesis phase:

- **`builds_on`** — becomes edges in the lineage DAG. Lets `build_lineages.py` reconstruct "which paper improved upon which" within each category.
- **`limitation`** — becomes the **next-step hook** for idea generation. Every good research idea should answer "what limitation of the current frontier does this address?" — and the limitation has to come from the paper itself, not from Claude's speculation.

Without these two fields, the synthesis phase tends to produce generic, ungrounded ideas ("someone should do process reward for X"). With them, every idea is anchored to a specific chain: "the frontier of Chain 1 admits limitation L; the next logical step is to address L by doing N".

---

## How to launch in parallel

Split total batches into chunks of 6 per agent, launch 5-8 agents via Agent tool with `run_in_background=true`.

```
For 36 batches:
  Agent 1: b_01-06
  Agent 2: b_07-12
  Agent 3: b_13-18
  Agent 4: b_19-24
  Agent 5: b_25-30
  Agent 6: b_31-36
```

---

## Failure recovery

If a batch range fails (Usage Policy, API error, timeout):

1. **Split into single batches** — launch one agent per batch
2. **Use English-only prompts** — avoid Chinese for sensitive topics (safety/adversarial)
3. **Reframe as "academic analysis"** in the prompt
4. **Retry with a different agent ID** (don't SendMessage to the failed one)
