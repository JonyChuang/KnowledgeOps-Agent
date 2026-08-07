# KnowledgeOps Agent 项目交接文档

**交接日期：** 2026-08-07  
**仓库路径：** `D:\Agent\CoreCoder`  
**当前项目：** 在原 CoreCoder 基础上改造的 KnowledgeOps Agent  
**当前阶段：** 第三阶段已完成，准备进入第四阶段

## 1. 新窗口阅读顺序

新窗口接手时，请先按以下顺序阅读：

1. 本文件：`docs/knowledgeops-handoff.md`
2. 完整学习记录：`docs/knowledgeops-learning-log.md`
3. 项目配置：`pyproject.toml`、`.env`（只查看变量名和非敏感配置，不要输出 API Key）
4. 第三阶段核心代码：`knowledgeops/rag/`、`knowledgeops/services/indexing.py`、`knowledgeops/tasks/indexing.py`
5. 第四阶段交付计划：学习记录中的“一周交付计划”表格

接手后的工作方式必须延续当前约定：先说明要改的文件、代码位置、项目作用和修改原因，再让用户手动修改；每次完成后补充学习日志。除非用户明确要求，不要直接替用户修改业务代码。

## 2. 项目背景与技术结论

本项目最初是 CoreCoder，一个 CLI Coding Agent。改造后新增了独立的 `knowledgeops/` 应用包，用于企业知识库、文档索引、语义检索和后续 Agent 工作流。

当前项目不是 LangChain 项目，也还没有接入 LangGraph。现阶段使用的是：

- FastAPI：HTTP 服务和 REST API
- SQLAlchemy Async：异步数据库访问
- SQLite：本地开发和自动化测试
- PostgreSQL：计划中的容器化部署数据库
- Alembic：数据库迁移
- pypdf：PDF 文本提取
- OpenAI-compatible Embeddings 封装：统一调用 Embedding API
- 智谱 BigModel：当前实际使用的 Embedding 服务
- Qdrant Cloud：向量存储和向量相似度召回
- pytest：自动化测试
- Ruff：Python 静态检查

LangGraph 计划在第五阶段接入，用于把知识库问答、工单查询、建单确认等能力组织成 Agent 工作流。第四阶段先完善检索质量，不要提前引入 LangGraph。

## 3. 已确认完成的内容

### 第三阶段 RAG 主链路

第三阶段最终验收已经通过，当前完成度记录为 100%。已实现：

1. 文本、Markdown 和 PDF 文档解析。
2. 文本规范化和 Chunk 切分。
3. `DocumentChunk` 数据库存储。
4. Embedding Provider 抽象和确定性测试 Provider。
5. Qdrant Collection 自动创建、维度校验和向量写入。
6. 按 `knowledge_base_id` 过滤的向量查询。
7. 文档索引任务和 `uploaded -> indexing -> ready/failed` 状态流转。
8. `SemanticRetriever`，把用户问题转换为查询向量并返回结构化引用。
9. `POST /api/v1/knowledge-bases/{knowledge_base_id}/search` 检索 API。
10. Qdrant Cloud 真实连接、认证、写入和读取验证。
11. 真实端到端 Markdown 索引与检索演示。

### 自动化验证

在正确的 `myagent` 环境中，最近一次全量测试结果为：

```text
126 passed in 19.26s
```

KnowledgeOps 代码静态检查结果为：

```text
conda run -n myagent python -m ruff check knowledgeops
All checks passed!
```

全量 `ruff check knowledgeops tests` 仍会检查到原 CoreCoder 测试文件中的格式和规则问题。这些问题不影响 pytest 运行，也不是第四阶段的业务阻塞项；如果后续要达到全仓库静态检查全绿，再单独整理 `tests/test_core.py`、`tests/test_demo.py`、`tests/test_embeddings.py` 等旧测试文件。

### 真实端到端演示

运行命令：

```powershell
python scripts/demo_knowledgeops_rag.py
```

成功输出的关键内容：

```text
Indexed status: ready
Chunk count: 1
Search results:
- score=0.4821 source=aurora-api-handbook.md chunk=0
```

这说明：演示文档已经完成解析、切分、Embedding、Qdrant Cloud 写入，用户问题也完成向量化，并返回带来源的检索片段。

## 4. 已解决的重要问题

### Qdrant payload 索引错误

曾出现：

```text
Index required but not found for "knowledge_base_id"
```

原因是 Qdrant Cloud 在使用 `knowledge_base_id` 过滤查询时要求该字段存在 payload index。现在 `knowledgeops/rag/vector_store.py` 的 `ensure_collection()` 会调用 `_ensure_payload_indexes()`，创建 `knowledge_base_id` 的 `KEYWORD` 索引。

### Retriever 循环导入

曾经在 `knowledgeops/rag/retriever.py` 中从包级入口导入 `QdrantVectorStore`，导致 `knowledgeops.rag` 尚未初始化完成时再次导入自身。现在使用同目录相对导入：

```python
from .embeddings import EmbeddingProvider
from .vector_store import QdrantVectorStore, VectorSearchResult
```

测试代码必须放在 `tests/test_retriever.py`，不要放进生产模块。

### Embedding 代理商错误

之前 OpenAI-compatible 代理返回过 503 和 `model_not_found`。问题发生在 Embedding 服务或代理商，不是 Qdrant Cloud。当前已切换到智谱接口并完成真实演示，`.env` 中的模型名是 `embedding-3`。

不要在代码、日志或交接文档中记录真实 API Key。之前截图中曾暴露过 Key，建议用户在对应平台轮换该 Key。

### Python 环境问题

项目依赖应在 `myagent` 环境中运行。推荐先激活环境：

```powershell
conda activate myagent
python scripts/demo_knowledgeops_rag.py
python -m pytest -q
python -m ruff check knowledgeops
```

如果出现 `ModuleNotFoundError: No module named 'knowledgeops'`，先确认当前目录是 `D:\Agent\CoreCoder`，并确认命令使用的是 `myagent` 环境的 Python。必要时在该环境重新执行：

```powershell
python -m pip install -e ".[dev]"
```

不要把默认 Anaconda 环境中缺少依赖的结果当成项目代码失败。

## 5. 重要文件索引

### 配置和启动

- `pyproject.toml`：项目依赖、构建包和命令入口
- `.env`：本地敏感配置，已被 Git 忽略，不提交、不复制 Key
- `knowledgeops/config.py`：数据库、Qdrant、Embedding 模型和维度配置
- `knowledgeops/api/app.py`：FastAPI 应用工厂和路由注册
- `knowledgeops/main.py`：Uvicorn 启动入口

### 数据层

- `knowledgeops/db.py`：异步 Engine、Session 和建表
- `knowledgeops/models/`：知识库、文档、Chunk、审计事件 ORM 模型
- `knowledgeops/repositories/`：数据库查询和持久化封装
- `knowledgeops/services/knowledge.py`：知识库和文档业务规则
- `knowledgeops/services/indexing.py`：文档解析、切分、Embedding、向量写入和状态流转
- `migrations/`：Alembic 数据库迁移

### RAG 和任务

- `knowledgeops/rag/parser.py`：文本、Markdown、PDF 解析
- `knowledgeops/rag/chunker.py`：文本切分
- `knowledgeops/rag/embeddings.py`：Embedding Provider 协议、确定性 Provider、OpenAI-compatible Provider
- `knowledgeops/rag/vector_store.py`：Qdrant Collection、payload index、upsert 和向量 search
- `knowledgeops/rag/retriever.py`：问题向量化和引用结果转换
- `knowledgeops/tasks/indexing.py`：生产依赖组装、索引任务和 Retriever 工厂

### API 和测试

- `knowledgeops/api/routers/knowledge_bases.py`：知识库、文档和搜索 API
- `knowledgeops/schemas/knowledge.py`：请求和响应 Schema
- `tests/test_rag.py`：解析、切分和 PDF 测试
- `tests/test_vector_store.py`：Qdrant 内存模式、过滤和维度测试
- `tests/test_retriever.py`：语义检索器测试
- `tests/test_full_indexing.py`：数据库到向量库的端到端离线测试
- `tests/test_knowledge_base_api.py`：知识库和搜索 API 集成测试
- `scripts/verify_qdrant_cloud.py`：真实 Qdrant Cloud 连通性检查
- `scripts/demo_knowledgeops_rag.py`：真实 Embedding + Qdrant Cloud RAG 演示

## 6. 当前配置约束

当前 `.env` 使用智谱兼容接口，配置逻辑如下：

```text
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
EMBEDDING_MODEL=embedding-3
EMBEDDING_DIMENSIONS=512
QDRANT_COLLECTION=knowledgeops_chunks_zhipu
```

具体 API Key 只保留在本地 `.env` 中，交接文档不得写出。Embedding 维度改变时，必须新建 Qdrant Collection 或重建旧 Collection，不能把不同维度的向量混用。

## 7. 未完成事项

第三阶段没有剩余阻塞项。未完成事项属于第四阶段及之后：

1. Elasticsearch 关键词/BM25 召回。
2. Qdrant 向量召回与 Elasticsearch 结果通过 RRF 融合。
3. Rerank 模型或可替换 Reranker。
4. Recall@5、MRR、检索耗时等离线评测。
5. 第五阶段的 LangGraph Agent 工作流和工单协同。
6. 第六阶段的 Celery、前端管理台和 Docker Compose 完整部署。
7. 第七阶段的 Neo4j GraphRAG、可观测性、评测页面和演示文档。

## 8. 下一步动作：第四阶段第一小步

第四阶段目标是提升检索质量，而不是重写已经通过验收的语义检索链路。

建议第一小步按以下顺序执行：

1. 新增 `knowledgeops/rag/keyword_store.py`，先定义 Elasticsearch/BM25 关键词召回的接口和结果结构。
2. 新增 `knowledgeops/rag/hybrid.py`，实现 Qdrant 结果与 BM25 结果的统一候选结构。
3. 新增 `knowledgeops/rag/fusion.py`，实现 Reciprocal Rank Fusion（RRF）。
4. 用纯内存的 Fake KeywordStore 和现有 Fake/Memory Qdrant 编写测试，先验证排序逻辑，不依赖 Elasticsearch 服务。
5. 在 `docs/knowledgeops-learning-log.md` 增加“第四阶段第一小步”，记录每个文件的作用、设计原因和测试结果。

RRF 的核心公式：

```text
RRF_score(document) = sum(1 / (k + rank_i))
```

其中 `rank_i` 是文档在某个召回器中的名次，`k` 是防止头部排名权重过大的常数。第四阶段必须保留 `knowledge_base_id` 隔离，不能因为增加 BM25 而跨知识库召回。

## 9. 接手后的第一轮检查

新窗口在修改代码前执行：

```powershell
Set-Location D:\Agent\CoreCoder
conda activate myagent
python -m pytest -q
python -m ruff check knowledgeops
git status --short
```

如果全量测试不是 `126 passed`，先定位回归原因，不要直接开始第四阶段。确认基线后，再按照第 8 节的第一小步由用户手动实现。

