# Lineage + Idea Example — 学习样本

这是一个完整的 **lineage-grounded idea** 示例。Claude 在 synthesis 阶段应该照这个格式产出 findings.json 和 ideas.json。

---

## ✅ GOOD: 完整锚定到演化链的 idea

### Lineage trace (来自 build_lineages.py 自动构造)

**Category**: 流式视频理解 — Memory 机制
**Chain**: "Dense → Sparse → Event → Agentic" 演化

```
2024.06 MA-LMM — 首次引入 memory augmentation
   ↓ [admitted limitation: "memory size grows linearly with video length"]
2024.12 Flash-VStream — Star Memory + STM/LTM 两级
   ↓ [admitted limitation: "information loss under aggressive compression"]
2025.06 StreamForest — Persistent event memory，引入 event boundary
   ↓ [admitted limitation: "event boundary is heuristic, not learned"]
2025.10 EventMemAgent — Event graph + Agentic RL (ReAct 多轮)  ← 当前 frontier
        admitted limitation: "event extraction 仍依赖 LLM hallucinate 产生边界"
```

### Idea grounded in the chain

```json
{
  "id": "S1",
  "title": "Contrastive Event Boundary Learning for Streaming Video Memory",
  "tier": "S",
  "lineage": {
    "category": "流式视频理解",
    "chain_name": "Memory 机制演化 (Dense → Sparse → Event → Agentic)"
  },
  "frontier_paper": {
    "title": "EventMemAgent: Hierarchical Event-Centric Memory for Online Video Understanding with Adaptive Tool Use",
    "arxiv_id": "2602.15329",
    "date": "2026-02",
    "venue": "arxiv",
    "limitation": "event extraction 仍依赖 LLM 产生 event 边界，存在 hallucinate 和 drift"
  },
  "addresses_limitation": "用对比自监督学习一个轻量 event boundary head，替换 LLM 产 event 的环节，消除 LLM hallucinate 作为 memory 错误源",
  "why_next_step": "这条 chain 从 MA-LMM 的 dense memory → Flash-VStream 的 sparse → StreamForest 的 event → EventMemAgent 的 agentic graph，每一步都在让 memory 更结构化。下一步必然是让 event boundary 本身从数据里学出来，因为 EventMemAgent 已经证明 event 作为 memory 单位是对的，但 boundary 质量成为瓶颈。这不是凭空的 idea，是这条 chain 的物理延续。",
  "technical_approach": "(1) 用 InfoNCE 在 Ego4D / HowTo100M 上训练一个 boundary predictor：正样本是跨 event 的 clip pair，负样本是同 event 内的 clip pair；(2) 把 predictor 插入 EventMemAgent 的 memory 构建 pipeline，替换其 LLM-based event extraction；(3) 冻结 EventMemAgent 的其他部分，只训 boundary head (轻量 1M 参数) 和必要的 adapter。",
  "benchmark": "StreamingBench / OVO-Bench / Ego4D Episodic Memory NLQ",
  "baselines": "EventMemAgent (2602.15329), StreamForest (NeurIPS 2025), Flash-VStream (ICCV 2025)",
  "expected_outcome": "StreamingBench +3-5% over EventMemAgent；消融显示 learned boundary 降低 event drift rate 40%+",
  "one_month_milestone": "复现 EventMemAgent 的 memory 构建流程，插入一个 random-init boundary head 验证端到端 pipeline 跑通；在 StreamingBench 的 10% 子集上跑一次 baseline 数字",
  "target_venue": "NeurIPS / CVPR",
  "why_now": "EventMemAgent 2026-02 刚出，limitation 明确写在 conclusion 里。Ego4D/HowTo100M 的 event boundary 数据成熟。Contrastive SSL 在视频侧 (VideoMAE-v2, V-JEPA) 已经 2 年成熟。"
}
```

---

## ❌ BAD: Ungrounded ideas (these fail verify_synthesis.py)

### Bad example 1 — 太空泛，没锚定 lineage

```
Idea: "Video LLM 需要更好的记忆机制"

为什么不好:
- 没有 lineage chain
- 没有具体的 frontier paper
- "更好的" 是 motherhood statement
- 没说要改什么 limitation
- 没 benchmark / milestone
```

### Bad example 2 — 伪装成具体但仍然 ungrounded

```
Idea: "用 Transformer 处理流式视频"

为什么不好:
- 没有引用任何 frontier paper
- 没有说是从哪条 chain 来的
- 这是 2020 年就在做的，不是 "next step"
- 不是针对 admitted limitation 的改进
```

### Bad example 3 — 编造数字

```
Idea: "...因为 80% 的 Video LLM 都不能处理长视频..."

为什么不好:
- "80%" 数字没在 all_merged.json 里能验证
- verify_synthesis.py 会 flag 这种编造的统计
- 应该写 "X of Y papers (以具体的 arxiv_id 为证据)"
```

---

## Ideas 的 5 条硬性规则

1. **Lineage required**: 必须指向 lineages.json 里存在的 category + chain_name
2. **Frontier required**: frontier_paper 必须能 fuzzy match 到 all_merged.json 里的某一篇
3. **Limitation required**: frontier_paper 必须有非空 limitation（即原论文作者自己承认的局限）
4. **Addresses_limitation required**: 必须明确说这个 idea 怎么解决这个 limitation
5. **Why_next_step required**: 必须说清楚为什么这是从 chain 物理延续出来的下一步，不是拍脑袋

任何 idea 违反上述规则之一 → verify_synthesis.py reject → render_synthesis.py 不会渲染它。

---

## 为什么这个格式产生好 ideas

- **Lineage 提供物理延续性**：idea 不再是"随便找个 gap"，而是"站在前人肩膀上的一小步"
- **Admitted limitation 提供 ground truth**：不是 Claude 猜测的 gap，而是原论文作者自己承认的局限
- **Addresses_limitation + why_next_step 强制因果推理**：你必须解释为什么这是那个 limitation 的解药
- **One_month_milestone 强制可行性**：不能只有 vision，必须有第一步

这比之前"找 gap 填 gap"的 idea 生成方法强一个量级，因为 gap 来源本身是可验证的。
