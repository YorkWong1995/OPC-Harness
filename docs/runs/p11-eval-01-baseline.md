# P11-EVAL-01 评测基线报告

> 任务：将 RAG 评测管道从 BM25 单路接入 BM25 + Vector + RRF 完整路径，并记录基线指标作为后续所有优化的对比参考。

## 评测配置

| 项 | 值 |
|---|---|
| 评测集 | `tests/fixtures/rag_eval_dataset.json` |
| 查询总数 | 26（24 条有答案 + 2 条 no_answer 拒答） |
| 语料 chunk 数 | 334 |
| top_k | 5 |
| 向量模型 | ONNXMiniLM_L6_V2（minilm，384 维） |
| 向量后端 | FAISS IndexFlatL2 |

评测指标在 24 条有答案查询上计算（no_answer 单独统计拒答正确率）。

## 基线指标对比

| 管道 | hit_rate | MRR | nDCG | hits/scored | no_answer 正确 |
|---|---|---|---|---|---|
| BM25 单路 | **0.750** | **0.521** | 0.564 | 18/24 | 2/2 |
| BM25+Vector+RRF | 0.583 | 0.497 | 0.524 | 14/24 | 2/2 |

复现命令：

```bash
python scripts/run-rag-eval.py --pipeline bm25 --top-k 5 --output docs/runs/p11-eval-01-baseline-bm25.json
python scripts/run-rag-eval.py --pipeline rrf  --top-k 5 --output docs/runs/p11-eval-01-baseline-rrf.json
```

## 关键发现

1. **完整 RRF 管道当前低于 BM25 单路**。根因是 `Retriever.expand_context()` 会在原始命中结果中插入邻居 chunk 和依赖文件首块，这些扩展项挤占了 top_k 名额，把真正相关的命中挤出前 5。这是评测覆盖完整路径后才暴露出来的问题。
2. **本项目语料以中文问答 + 精确符号名为主，BM25 词项匹配本就强**；向量召回在 minilm（英文模型）下对中文语义匹配偏弱，RRF 融合反而引入噪声。
3. nDCG 修正：早期实现的 IDCG 分母按声明相关文件数计算，而 expand_context 注入同文件多 chunk 导致 DCG 超过 IDCG（nDCG>1）。已修正为评测仅取 top_k、IDCG 按 max(声明数, 实际命中数) 计算。

## 对后续任务的指引

- **P11-FILTER-01（Metadata Filter）**：按 language/source_name 过滤可减少向量召回噪声。
- **P11-RERANK-01（Rerank）**：在 expand_context 之前用 reranker 对 RRF top-30 重排，是修复"扩展项挤占名额"的正解——先选准 top-k 再扩展上下文。
- **P11-CTX-01（Contextual Retrieval）**：为 embedding 输入加文件路径/语言前缀，提升向量召回对代码意图的命中。

后续每项优化均以本基线（BM25 hit_rate=0.75 为强基线，RRF=0.583 为可优化起点）作对比。
