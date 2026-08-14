# KnowledgeOps Agent 项目交接文档

**交接日期：** 2026-08-08
**仓库路径：** `D:\Agent\CoreCoder`
**当前分支：** `codex/knowledgeops-agent`
**当前阶段：** 第四阶段已完成，下一步进入第五阶段 LangGraph Agent 工作流

## 1. 新窗口阅读顺序

新窗口接手时，按以下顺序阅读：

1. 本文件：`docs/knowledgeops-handoff.md`
2. 完整学习记录：`docs/knowledgeops-learning-log.md`
3. 项目配置：`pyproject.toml`、`.env`。只查看变量名和非敏感配置，绝不输出 API Key。
4. 第四阶段核心目录：`knowledgeops/rag/`、`knowledgeops/evaluation/`、`knowledgeops/tasks/indexing.py`
5. HTTP 接口：`knowledgeops/api/routers/knowledge_bases.py`、`knowledgeops/schemas/knowledge.py`

工作方式必须延续以下约定：

- 用户手动修改所有业务代码；助手先说明完整文件路径、代码位置、作用和修改原因，再让用户修改。
- 助手负责维护 `docs/knowledgeops-learning-log.md`；未经用户明确要求，不直接修改业务代码。
- 每个功能必须先有聚焦测试，再跑全量 pytest。不要为了消除本地 Qdrant 的 warning 删除生产所需的 payload index 代码。

## 2. 项目背景与当前技术栈

本项目源自 CoreCoder CLI Coding Agent。新增的 `knowledgeops/` 是独立的企业知识库应用包，负责知识库管理、文档索引、混合检索和后续 Agent 工作流；不要把新业务逻辑写入 `corecoder/`。

当前技术栈：

- FastAPI：REST API。
- SQLAlchemy Async、SQLite：本地开发和测试数据层。
- PostgreSQL、Alembic：后续容器化部署数据层。
- OpenAI-compatible Embedding Provider：当前本地配置使用智谱兼容接口。
- Qdrant Cloud：向量索引与语义召回。
- Elasticsearch：BM25 关键字召回。
- pytest、pytest-asyncio：自动化验证。
- Ruff：KnowledgeOps 静态检查。

项目当前不是 LangChain 或 LangGraph 项目。LangGraph 应从第五阶段开始接入，不要提前把 Agent 状态、检索和存储实现耦合在一起。

## 3. 已确认完成的内容

### 阶段 1 至阶段 3

已完成 FastAPI 服务骨架、知识库和文档 API、异步数据层、文本/Markdown/PDF 解析、Chunk 切分、Embedding、Qdrant 索引、文档状态流转、SemanticRetriever 和真实 Qdrant Cloud 演示。

文档状态流转为：

```text
uploaded -> indexing -> ready
                    -> failed
```

### 阶段 4：检索质量闭环

第四阶段已完成，当前检索链路为：

```text
DocumentChunk
  -> Qdrant 向量索引 + Elasticsearch 文本索引
  -> 语义召回 + BM25 召回
  -> HybridCandidate 归一化与知识库隔离
  -> Reciprocal Rank Fusion
  -> TokenOverlapReranker 二次排序
  -> citable HybridRetrievedChunk
  -> POST /api/v1/knowledge-bases/{knowledge_base_id}/search
```

离线评估模块已经提供宏平均 `Recall@k`、`MRR` 和平均检索耗时。

## 4. 重要架构结论

1. `DocumentChunk.id` 是跨系统稳定身份：Qdrant 使用 `vector_id`，Elasticsearch 使用 `_id`，融合和 API 使用 `chunk_id`。
2. `knowledge_base_id` 必须在每层保持隔离：Qdrant payload filter、Elasticsearch term filter、候选转换校验和检索 API 路径范围。
3. 向量相似度与 BM25 原始分数不能相加；RRF 只依据各自排名进行融合。
4. RRF 对同一召回列表中的重复 Chunk 使用有效排名去重，不能因重复结果增加分数或压低后续候选排名。
5. 文档索引同时写入 Qdrant 与 KeywordStore；任一路失败都将文档标记为 `failed`。当前没有跨服务事务或补偿删除机制。
6. Rerank 在 RRF 之后运行。启用 Reranker 时，HybridRetriever 会先从两路召回最多 20 个候选，再返回用户请求的 `limit` 条，避免“先截断、后重排”失去选择空间。
7. `TokenOverlapReranker` 是可运行的确定性基线，实现了 `Reranker` Protocol；未来可替换为 Cross-Encoder 或供应商模型，不应改变 HybridRetriever 或 API 契约。
8. 搜索 API 公开 `chunk_id`、`score`、`rerank_score`、`sources` 和引用字段。`score` 是 RRF 分数，`rerank_score` 是二次排序分数。

## 5. 关键文件索引

### 配置、数据与索引

- `knowledgeops/config.py`：数据库、Embedding、Qdrant 与 Elasticsearch 配置。
- `knowledgeops/services/indexing.py`：解析、切分、Embedding、双写索引和文档状态处理。
- `knowledgeops/tasks/indexing.py`：Qdrant、Elasticsearch、SemanticRetriever、HybridRetriever 的生产工厂。
- `knowledgeops/rag/vector_store.py`：Qdrant collection、维度校验、payload index、upsert 和过滤查询。
- `knowledgeops/rag/elasticsearch_keyword_store.py`：Elasticsearch mapping、Chunk 写入、BM25 match 查询和资源关闭。

### 检索与评估

- `knowledgeops/rag/keyword_store.py`：KeywordStore、KeywordPoint、KeywordSearchResult 契约。
- `knowledgeops/rag/hybrid.py`：向量/BM25 结果转换为统一 HybridCandidate，并校验知识库边界。
- `knowledgeops/rag/fusion.py`：重复安全的 RRF 实现。
- `knowledgeops/rag/retriever.py`：SemanticRetriever；`retrieve_vector_results()` 供混合检索复用。
- `knowledgeops/rag/hybrid_retriever.py`：并行双路召回、RRF、Rerank、可引用输出和资源关闭。
- `knowledgeops/rag/reranker.py`：Reranker Protocol 与 TokenOverlapReranker 基线。
- `knowledgeops/evaluation/retrieval.py`：EvaluationCase、RetrievalMetrics、`evaluate_retriever()`。

### API 与测试

- `knowledgeops/api/routers/knowledge_bases.py`：知识库、文档、混合搜索 API。
- `knowledgeops/schemas/knowledge.py`：搜索请求和响应 Schema。
- `tests/test_hybrid_retriever.py`：双路召回、RRF、引用字段和参数边界。
- `tests/test_reranker.py`：术语覆盖重排和 limit 校验。
- `tests/test_evaluation.py`：Recall@k、MRR、延迟和空评估集校验。
- `tests/test_knowledge_base_api.py`：搜索 API 调用 HybridRetriever、响应映射与资源关闭。
- `tests/test_full_indexing.py`、`tests/test_indexing_task.py`：双写、失败状态和运行时工厂。

## 6. 当前验证基线

必须在 `myagent` 环境和仓库根目录执行：

```powershell
Set-Location D:\Agent\CoreCoder
conda activate myagent
python -m ruff check knowledgeops
python -m pytest -q
git diff --check
```

当前已确认结果：

```text
ruff check knowledgeops: passed
pytest: 152 passed, 1 warning
git diff --check: no trailing whitespace
```

唯一 warning 来自本地内存 Qdrant：payload index 在内存模式无效果。生产 Qdrant Cloud 需要此索引，保留 `vector_store.py` 中的生产代码不变。

不要用系统默认 Anaconda Python 运行 Ruff；它缺少 Ruff 依赖。终端必须显示 `(myagent)`，或使用 `conda run -n myagent`。

`ruff check knowledgeops tests` 仍会报告旧 CoreCoder 测试中的历史问题，例如 `tests/test_core.py`、`tests/test_demo.py`、`tests/test_migrations.py`。这些不属于第四阶段变更；未经用户要求，不要对整个旧测试集执行 `ruff --fix`。

## 7. 当前工作区状态

第四阶段的业务代码、测试和学习日志均尚未提交，工作区有预期中的修改和新增文件。不要使用 `git reset --hard`、`git checkout --` 或其他方式清除这些变更。

学习日志是第四阶段逐步设计和测试证据的完整记录：`docs/knowledgeops-learning-log.md`。

## 8. 未完成事项与第五阶段入口

第四阶段没有剩余业务阻塞项。后续范围：

1. 第五阶段：LangGraph Agent 工作流和工单协同。
2. 第六阶段：Celery 异步任务、前端管理台、Docker Compose，以及真实 Elasticsearch 容器联调。
3. 第七阶段：Neo4j GraphRAG、可观测性、评测页面和演示文档。

第五阶段的第一小步不是直接创建复杂图，而是先定义 Agent 的状态和边界：

1. 新建 `knowledgeops/agents/`，定义可序列化的 Agent state 和用户意图类型。
2. 明确三条初始路径：知识库问答、工单查询、创建工单。
3. 创建工单必须经过显式确认节点；查询和问答不得产生写操作。
4. 将 HybridRetriever 作为只读工具注入 Agent，不在节点中重复实现检索、RRF 或 Rerank。
5. 为路由、确认和工具调用先写离线测试，再接入 LangGraph 依赖和具体图实现。

## 9. 安全与配置约束

`.env` 仅保存在本地，不提交。交接文档、测试输出、截图和日志均不得记录真实 API Key、数据库密码或内部业务文档内容。

Embedding 维度变化时必须新建或重建 Qdrant collection；不同维度的向量不得写入同一 collection。
