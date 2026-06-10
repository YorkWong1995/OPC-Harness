# P11: RAG 系统优化

> 目标：基于 RAG 由浅入深分享文档（docs/RAG_由浅入深分享.md）的理论框架，针对本项目代码 RAG 系统的现状缺口，系统性提升检索准确率、降低噪声、完善评测闭环。
> 优化方向：评测管道补全 → Metadata Filter 启用 → Rerank 引入 → Contextual Retrieval → Code Summary chunk → 增量索引。
> 设计原则：按优先级逐步落地，每步有可量化的评测基线对比；不引入 GraphRAG、RAPTOR 等当前场景收益有限的重型能力。

---

## 现状速览

| 能力 | 现状 |
|---|---|
| Hybrid Search（BM25 + Vector + RRF） | 已有 |
| Query Rewrite（代码意图识别） | 已有（启发式偏置，非 LLM 改写） |
| Metadata Filter | 字段已存，**未启用** |
| Rerank | **无** |
| 评测管道 | 框架已有，**仅覆盖 BM25 单路** |
| Contextual Retrieval | **无** |
| Code Summary chunk | **无** |
| 增量索引 | file_hash 字段已有，**是否真正跳过未验证** |

---

## 1. P0 - 评测基线补全

- [x] P11-EVAL-01 将评测管道接入完整 RRF 管道 <!-- files: src/opc/knowledge/rag_eval.py, scripts/run-rag-eval.py, tests/fixtures/rag_eval_dataset.json --> <!-- context: 责任角色=Engineer/QA；输入=现有 rag_eval.py（仅 BM25 单路）、Retriever.retrieve() 完整管道；输出=评测脚本改为调用 Retriever.retrieve()，并记录 hit_rate/MRR/nDCG 基线数值；完成标准=评测覆盖 BM25+Vector+RRF 完整路径，输出基线报告作为后续所有优化的对比参考 --> <!-- depends_on: none --> <!-- read_before_start: tasks-p11.md P11-EVAL-01、src/opc/knowledge/rag_eval.py、src/opc/knowledge/retriever.py、scripts/run-rag-eval.py、tests/fixtures/rag_eval_dataset.json --> <!-- execution: main --> <!-- evidence: docs/runs/p11-eval-01-baseline.md, docs/runs/p11-eval-01-baseline-bm25.json, docs/runs/p11-eval-01-baseline-rrf.json；rag_eval.run_rag_eval 新增 use_full_pipeline 走 Retriever.retrieve()，run-rag-eval.py 加 --pipeline；基线 BM25 hit_rate=0.75/MRR=0.521，RRF hit_rate=0.583/MRR=0.497（top5,24题） --> <!-- handoff: RRF 当前低于 BM25，根因 expand_context 挤占 top_k，留待 RERANK 修复 -->

- [x] P11-EVAL-02 评测集补充 expected_chunk_ids 和问题分类 <!-- files: tests/fixtures/rag_eval_dataset.json --> <!-- context: 责任角色=QA；输入=P11-EVAL-01 基线报告、现有评测集（只有 question + relevant_files）；输出=评测集新增 expected_chunk_ids、category（code_symbol/doc_concept/cross_file/no_answer）字段；完成标准=覆盖至少 5 种问题类型，包含拒答场景 --> <!-- depends_on: P11-EVAL-01 --> <!-- read_before_start: tasks-p11.md P11-EVAL-02、P11-EVAL-01 evidence、tests/fixtures/rag_eval_dataset.json、docs/RAG_由浅入深分享.md §4.11 --> <!-- execution: main --> <!-- evidence: rag_eval_dataset.json 26 题，每题加 category+expected_chunk_ids；类别覆盖 code_symbol/doc_concept/cross_file/no_answer；新增 2 条 no_answer 拒答场景，rag_eval 对 no_answer 单独统计拒答正确率（2/2） --> <!-- handoff: -->


---

## 2. P0 - Metadata Filter 启用

- [x] P11-FILTER-01 在 Retriever.retrieve() 增加 filters 参数 <!-- files: src/opc/knowledge/retriever.py, src/opc/knowledge/vector_store.py, src/opc/tools/knowledge_tools.py --> <!-- context: 责任角色=Engineer；输入=现有 retriever.py（无过滤）、ChromaDB 后端已存 language/source_name 字段；输出=retrieve() 接受可选 filters dict，传入 ChromaDB where 条件；FAISS 后端在内存中按元数据后过滤；完成标准=能按 language、source_name 过滤，knowledge_tools 的 search_knowledge 工具透传 filters 参数 --> <!-- depends_on: P11-EVAL-01 --> <!-- read_before_start: tasks-p11.md P11-FILTER-01、P11-EVAL-01 evidence、src/opc/knowledge/retriever.py、src/opc/knowledge/vector_store.py、src/opc/tools/knowledge_tools.py --> <!-- execution: main --> <!-- evidence: retrieve(filters=) 支持 language/source_name/file_path，标量=相等、列表=属于其一；FAISS 放宽召回后内存过滤(query_filtered)，Chroma 用 where($in/$and)；BM25 与 expand_context 结果内存同条件过滤；search_knowledge 工具+schema 透传 language/source_name；验证脚本确认 markdown/python 过滤无泄漏(FILTER_OK)，test_retriever_context_expansion+test_vector_store_faiss 7 passed --> <!-- handoff: 单一全局 filter 会损害混合类别评测，过滤用于工具按需调用而非全量评测 -->

---

## 3. P1 - Rerank 引入

- [ ] P11-RERANK-01 集成轻量 reranker（bge-reranker-base） <!-- files: src/opc/knowledge/retriever.py, src/opc/knowledge/embedder.py --> <!-- context: 责任角色=Engineer；输入=P11-EVAL-01 基线、现有 RRF 融合逻辑；输出=在 RRF top-30 之后、expand_context() 之前插入 reranker 打分，选出 top-k 进入上下文；reranker 通过环境变量 OPC_RERANKER_MODEL 控制，默认关闭；完成标准=启用后评测指标不低于基线，reranker 可选不破坏现有流程 --> <!-- depends_on: P11-EVAL-01, P11-FILTER-01 --> <!-- read_before_start: tasks-p11.md P11-RERANK-01、P11-EVAL-01 evidence、src/opc/knowledge/retriever.py、src/opc/knowledge/embedder.py --> <!-- execution: main --> <!-- evidence: --> <!-- handoff: -->

- [ ] P11-RERANK-02 评测 rerank 前后指标对比 <!-- files: scripts/run-rag-eval.py, docs/runs/ --> <!-- context: 责任角色=QA；输入=P11-RERANK-01 实现、P11-EVAL-01 基线报告；输出=开启/关闭 reranker 的评测对比报告；完成标准=报告记录 hit_rate/MRR/nDCG 变化，并说明 rerank 对哪类问题有效、对哪类无效 --> <!-- depends_on: P11-RERANK-01 --> <!-- read_before_start: tasks-p11.md P11-RERANK-02、P11-RERANK-01 evidence、P11-EVAL-01 evidence、scripts/run-rag-eval.py --> <!-- execution: qa_acceptance --> <!-- evidence: --> <!-- handoff: -->

---

## 4. P1 - Contextual Retrieval（Chunk 上下文化）

- [ ] P11-CTX-01 为 embedding 输入添加文件路径和函数上下文前缀 <!-- files: src/opc/knowledge/indexer.py, src/opc/knowledge/embedder.py --> <!-- context: 责任角色=Engineer；输入=现有 Indexer.build() 流程、chunk 携带 file_path/language/start_line；输出=embedding 时对 chunk 文本前缀拼接"文件: {file_path}，语言: {language}"等上下文，存储仍保留原始 chunk 文本不变；完成标准=embedding 输入包含上下文，存储和检索结果不受影响，评测指标不退步 --> <!-- depends_on: P11-EVAL-01 --> <!-- read_before_start: tasks-p11.md P11-CTX-01、P11-EVAL-01 evidence、src/opc/knowledge/indexer.py、src/opc/knowledge/embedder.py、src/opc/knowledge/chunker.py --> <!-- execution: main --> <!-- evidence: --> <!-- handoff: -->

---

## 5. P2 - Code Summary Chunk

- [ ] P11-SUMMARY-01 设计 Code Summary chunk 生成方案 <!-- files: src/opc/knowledge/chunker.py, src/opc/knowledge/indexer.py, docs/knowledge-retrieval-design.md --> <!-- context: 责任角色=Architect；输入=现有 CodeChunker、Indexer；输出=对每个函数/类 chunk 用 LLM 离线生成一句话功能描述，作为独立 summary chunk 加入索引，与原始 code chunk 保持 ID 映射；设计决策：summary chunk 是额外检索入口，命中后返回对应原始 code chunk；完成标准=方案明确 summary 生成时机、存储方式、与原始 chunk 的关联字段和增量触发条件 --> <!-- depends_on: P11-CTX-01 --> <!-- read_before_start: tasks-p11.md P11-SUMMARY-01、P11-CTX-01 evidence、src/opc/knowledge/chunker.py、src/opc/knowledge/indexer.py、docs/knowledge-retrieval-design.md --> <!-- execution: manual_review --> <!-- evidence: --> <!-- handoff: -->

- [ ] P11-SUMMARY-02 实现 Code Summary chunk 离线生成与索引 <!-- files: src/opc/knowledge/indexer.py, src/opc/knowledge/models.py, src/opc/knowledge/chunker.py --> <!-- context: 责任角色=Engineer；输入=P11-SUMMARY-01 方案；输出=Indexer 在构建索引时可选生成 summary chunk（由 OPC_CODE_SUMMARY=1 控制），summary chunk 携带 chunk_type=summary 和 source_chunk_id 字段；完成标准=默认不开启，开启后 summary chunk 进入向量索引，检索命中后自动关联原始 code chunk 一起返回 --> <!-- depends_on: P11-SUMMARY-01 --> <!-- read_before_start: tasks-p11.md P11-SUMMARY-02、P11-SUMMARY-01 evidence、src/opc/knowledge/indexer.py、src/opc/knowledge/models.py --> <!-- execution: main --> <!-- evidence: --> <!-- handoff: -->

- [ ] P11-SUMMARY-03 评测 Code Summary 对自然语言查询的提升 <!-- files: scripts/run-rag-eval.py, tests/fixtures/rag_eval_dataset.json, docs/runs/ --> <!-- context: 责任角色=QA；输入=P11-SUMMARY-02 实现、P11-EVAL-02 评测集（含 doc_concept 分类问题）；输出=开启/关闭 summary chunk 的评测对比，重点看自然语言描述功能类问题的 hit_rate 变化；完成标准=报告说明 summary chunk 对哪类查询有效 --> <!-- depends_on: P11-SUMMARY-02, P11-EVAL-02 --> <!-- read_before_start: tasks-p11.md P11-SUMMARY-03、P11-SUMMARY-02 evidence、P11-EVAL-02 evidence --> <!-- execution: qa_acceptance --> <!-- evidence: --> <!-- handoff: -->

---

## 6. P2 - 增量索引验证与完善

- [ ] P11-INC-01 验证并补全增量索引跳过逻辑 <!-- files: src/opc/knowledge/indexer.py, src/opc/knowledge/models.py --> <!-- context: 责任角色=Engineer；输入=现有 IndexMeta file_hash 字段；输出=确认 Indexer.build() 是否真正跳过未变更文件；若未实现则补全：文件 hash 未变时跳过 chunking+embedding，变更文件仅重建对应 chunk；完成标准=添加文件后只有新文件被重新 index，已有文件跳过；大规模代码库下重建时间显著降低 --> <!-- depends_on: P11-EVAL-01 --> <!-- read_before_start: tasks-p11.md P11-INC-01、src/opc/knowledge/indexer.py、src/opc/knowledge/models.py、src/opc/knowledge/index_paths.py --> <!-- execution: main --> <!-- evidence: --> <!-- handoff: -->

- [ ] P11-INC-02 支持文件删除时清理对应 chunk 和向量 <!-- files: src/opc/knowledge/indexer.py, src/opc/knowledge/vector_store.py, src/opc/knowledge/bm25_index.py --> <!-- context: 责任角色=Engineer；输入=P11-INC-01 增量逻辑；输出=索引重建时检测已删除文件，清理向量库和 BM25 索引中对应 chunk；完成标准=删除文件后重跑 index build，向量库和 BM25 中该文件的 chunk 不再出现 --> <!-- depends_on: P11-INC-01 --> <!-- read_before_start: tasks-p11.md P11-INC-02、P11-INC-01 evidence、src/opc/knowledge/indexer.py、src/opc/knowledge/vector_store.py、src/opc/knowledge/bm25_index.py --> <!-- execution: main --> <!-- evidence: --> <!-- handoff: -->

---

## 7. 阶段验收

- [ ] P11-ACCEPT-01 执行 P11 RAG 优化总体验收 <!-- files: tasks-p11.md, docs/runs/, src/opc/knowledge/ --> <!-- context: 责任角色=QA；输入=P11 全部已完成任务、评测对比报告；输出=P11 acceptance-check 验收报告；完成标准=验收覆盖评测基线、Filter/Rerank/CTX/Summary/增量索引各项，并给出 pass/fail/needs-info 结论和后续建议 --> <!-- depends_on: P11-RERANK-02, P11-SUMMARY-03, P11-INC-02 --> <!-- read_before_start: tasks-p11.md P11-ACCEPT-01、全部 P11 evidence、docs/runs/ --> <!-- execution: qa_acceptance --> <!-- evidence: --> <!-- handoff: -->
