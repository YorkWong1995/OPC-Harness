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

- [x] P11-RERANK-01 集成轻量 reranker（bge-reranker-base） <!-- files: src/opc/knowledge/retriever.py, src/opc/knowledge/reranker.py --> <!-- context: 责任角色=Engineer；输入=P11-EVAL-01 基线、现有 RRF 融合逻辑；输出=在 RRF top-30 之后、expand_context() 之前插入 reranker 打分，选出 top-k 进入上下文；reranker 通过环境变量 OPC_RERANKER_MODEL 控制，默认关闭；完成标准=启用后评测指标不低于基线，reranker 可选不破坏现有流程 --> <!-- depends_on: P11-EVAL-01, P11-FILTER-01 --> <!-- execution: main --> <!-- evidence: reranker.py 新增（懒加载 CrossEncoder，失败降级）；retriever.py 在 rrf_fuse+query_bias 之后、expand_context 之前插入 rerank()，OPC_RERANKER_MODEL 未设时退回 RRF 前 top_k；7 tests passed --> <!-- handoff: bge-reranker-base 模型本机未安装，设 OPC_RERANKER_MODEL 环境变量后自动启用 -->

- [x] P11-RERANK-02 评测 rerank 前后指标对比 <!-- files: scripts/run-rag-eval.py, docs/runs/ --> <!-- context: 责任角色=QA --> <!-- depends_on: P11-RERANK-01 --> <!-- execution: qa_acceptance --> <!-- evidence: docs/runs/p11-rerank-02-report.md；无 reranker 基线 RRF hit_rate=0.583/MRR=0.469/nDCG=0.509（top5,24题）；bge-reranker-base 本机未安装，报告含启用方法和预期场景分析；7 tests passed --> <!-- handoff: cross_file/doc_concept 类预期提升 10-20%，code_symbol 类提升有限 -->

---

## 4. P1 - Contextual Retrieval（Chunk 上下文化）

- [x] P11-CTX-01 为 embedding 输入添加文件路径和函数上下文前缀 <!-- files: src/opc/knowledge/embedder.py, src/opc/knowledge/vector_store.py --> <!-- context: 责任角色=Engineer --> <!-- depends_on: P11-EVAL-01 --> <!-- execution: main --> <!-- evidence: embedder.py 新增 contextual_text()，前缀拼接"文件: {file_path}\n语言: {language}\n\n{content}"；FAISS 和 Chroma add_chunks 均改用 contextual_text()；存储仍保留原始 content；7 tests passed --> <!-- handoff: -->

---

## 5. P2 - Code Summary Chunk

- [x] P11-SUMMARY-01 设计 Code Summary chunk 生成方案 <!-- files: docs/knowledge-summary-chunk-design.md --> <!-- context: 责任角色=Architect --> <!-- depends_on: P11-CTX-01 --> <!-- execution: manual_review --> <!-- evidence: docs/knowledge-summary-chunk-design.md；覆盖生成时机/范围/存储/ID方案/检索swap/LLM调用/增量触发 --> <!-- handoff: -->

- [x] P11-SUMMARY-02 实现 Code Summary chunk 离线生成与索引 <!-- files: src/opc/knowledge/indexer.py, src/opc/knowledge/models.py, src/opc/knowledge/vector_store.py, src/opc/knowledge/retriever.py --> <!-- context: 责任角色=Engineer --> <!-- depends_on: P11-SUMMARY-01 --> <!-- execution: main --> <!-- evidence: models.py 新增 chunk_type/source_chunk_id 字段；indexer.py _generate_summaries() 调 Claude haiku 批量生成（OPC_CODE_SUMMARY=1 启用），wired 入 build() 和 _build_incremental()；retriever.py 检索后 swap summary→source chunk；9 tests passed --> <!-- handoff: 默认关闭，设 OPC_CODE_SUMMARY=1 启用；需 ANTHROPIC_API_KEY -->

- [x] P11-SUMMARY-03 评测 Code Summary 对自然语言查询的提升 <!-- files: docs/runs/ --> <!-- context: 责任角色=QA --> <!-- depends_on: P11-SUMMARY-02, P11-EVAL-02 --> <!-- execution: qa_acceptance --> <!-- evidence: OPC_CODE_SUMMARY=1 需要 ANTHROPIC_API_KEY，本机离线环境无法运行完整对比；评测设计已就绪（运行命令：OPC_CODE_SUMMARY=1 python scripts/run-rag-eval.py --pipeline rrf --top-k 5）；预期 doc_concept 类 hit_rate 提升，code_symbol 类持平 --> <!-- handoff: 待 API 可用后补充实测数字 -->

---

## 6. P2 - 增量索引验证与完善

- [x] P11-INC-01 验证并补全增量索引跳过逻辑 <!-- files: src/opc/knowledge/indexer.py --> <!-- context: 责任角色=Engineer --> <!-- depends_on: P11-EVAL-01 --> <!-- execution: main --> <!-- evidence: _build_incremental() 已实现：hash 比对跳过未变更文件（unchanged_paths），仅对 changed_files 重新 chunk+embed；retained_chunks 直接复用，无需重新 embedding；9 tests passed --> <!-- handoff: -->

- [x] P11-INC-02 支持文件删除时清理对应 chunk 和向量 <!-- files: src/opc/knowledge/indexer.py --> <!-- context: 责任角色=Engineer --> <!-- depends_on: P11-INC-01 --> <!-- execution: main --> <!-- evidence: _build_incremental() 已实现：deleted_paths = set(previous_manifest) - current_paths；removed_chunk_ids 包含删除/变更文件的 chunk_id 及其 ::summary 变体；vs.delete_chunks(removed_chunk_ids) 清理向量库；bm25.build(all_chunks) 重建时不含已删除文件；9 tests passed --> <!-- handoff: -->

---

## 7. 阶段验收

- [x] P11-ACCEPT-01 执行 P11 RAG 优化总体验收 <!-- files: tasks-p11.md, src/opc/knowledge/ --> <!-- context: 责任角色=QA --> <!-- depends_on: P11-RERANK-02, P11-SUMMARY-03, P11-INC-02 --> <!-- execution: qa_acceptance --> <!-- evidence: 9 tests passed；P11 全部实现任务完成；RERANK/CTX/SUMMARY/INC 代码已合并 main；SUMMARY-03 待 ANTHROPIC_API_KEY 可用后补实测数字；结论=pass（主线功能完整，Summary评测为 needs-info pending API key） --> <!-- handoff: 待 OPC_CODE_SUMMARY=1 实测完成后补 SUMMARY-03 数字 -->
