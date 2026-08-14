# KnowledgeOps Agent 学习日志（三）：第六阶段

本文记录第六阶段的最终正确环境和实现结果。第五阶段的 Agent 工作流见 `docs/knowledgeops-learning-log-phase5.md`。本文不记录历史证书、包安装或本机环境排错过程。

## 1. 阶段目标

第六阶段将文档索引从 HTTP 请求中拆出，交给 Celery Worker 异步执行；同时提供可操作的前端管理台和 Docker Compose 本地联调环境。

完成后的主链路：

```text
前端（Nginx，localhost:8080）
  -> FastAPI
  -> PostgreSQL 保存知识库和文档状态
  -> Redis 投递 Celery 任务
  -> Celery Worker
  -> OpenAI 兼容 Embedding API
  -> Qdrant 向量索引 + Elasticsearch 关键词索引
  -> 文档状态 ready 或 failed
```

## 2. 正确运行环境

- 仓库：`D:\Agent\CoreCoder`
- Conda 环境：`myagent`
- Python：`3.11.15`
- Docker Desktop：使用 WSL2 后端。
- Docker 数据目录：`D:\DockerData\DockerDesktopWSL`。
- 前端访问地址：`http://localhost:8080`。
- 运行时敏感信息只放在 `.env`；日志和提交中不记录 API Key、数据库密码或其他密钥。

基础命令：

```powershell
Set-Location D:\Agent\CoreCoder
conda activate myagent
docker build --tag knowledgeops-agent:local .
docker compose up -d
docker compose ps
```

项目镜像由 `Dockerfile` 手动构建，当前 `docker-compose.yml` 使用 `image: knowledgeops-agent:local`。因此 `docker compose build` 显示 `No services to build` 时并不代表镜像已更新；代码或依赖变更后必须再次执行 `docker build --tag knowledgeops-agent:local .`。

## 3. Compose 架构

第六阶段的容器化基础服务如下：

| 服务 | 职责 |
| --- | --- |
| `postgres` | 保存知识库、文档、Chunk、工单和审计记录。 |
| `redis` | Celery 的消息 broker 与任务结果后端。 |
| `qdrant` | 向量存储和语义召回。 |
| `elasticsearch` | BM25 关键词索引与召回。 |
| `migrate` | 启动前执行 Alembic 数据库迁移，成功退出码为 `0`。 |
| `api` | FastAPI 服务，内部监听 `8000`。 |
| `worker` | Celery Worker，消费 `knowledgeops` 队列。 |
| `frontend` | Nginx 托管静态前端，并反向代理 API。 |

第七阶段新增的 Neo4j 不属于本阶段的完成范围，应记录在后续阶段日志中。

## 4. 异步索引设计

### 任务边界

`POST /api/v1/documents/{document_id}/index` 只负责校验文档并投递任务，立即返回 `202 Accepted`。它不等待 Embedding、Qdrant 或 Elasticsearch 完成，因此浏览器请求不会被长耗时模型调用占用。

Celery 任务 `knowledgeops.index_document` 在独立 Worker 中执行。Worker 自行创建数据库会话和外部客户端，不复用 HTTP 请求生命周期。

### 关键文件

| 文件 | 作用 |
| --- | --- |
| `knowledgeops/tasks/celery_app.py` | 定义 Celery 应用、Redis broker 与结果后端。 |
| `knowledgeops/tasks/celery_indexing.py` | 注册 `knowledgeops.index_document` 任务，并通过 `asyncio.run()` 调用异步索引逻辑。 |
| `knowledgeops/tasks/indexing.py` | 生产工厂：Qdrant、Elasticsearch、Embedding 和混合检索依赖。 |
| `knowledgeops/services/indexing.py` | 解析、Chunk 切分、向量写入、关键词写入、审计和状态迁移。 |
| `knowledgeops/api/routers/knowledge_bases.py` | 上传文档、查询文档状态、提交索引任务的 API。 |

### 状态机

```text
uploaded -> indexing -> ready
                    -> failed
```

只有 Qdrant 与 Elasticsearch 都成功写入后，文档才会变为 `ready`。任一路失败会记录错误并将文档标记为 `failed`。这保证前端状态能够准确反映异步任务的最终结果。

## 5. 前端管理台

前端代码位于 `knowledgeops/frontend/`：

| 文件 | 作用 |
| --- | --- |
| `index.html` | 知识库、文档索引和 Agent 视图的页面结构。 |
| `styles.css` | 管理台样式和状态颜色。 |
| `app.js` | 同源 API 调用、知识库创建、文档上传、索引投递和状态轮询。 |

前端使用相对地址 `const API_BASE = "/api/v1"`，由 Nginx 反向代理到 API，避免浏览器跨域问题。文档轮询以 `ready` 和 `failed` 为终止状态；`ready` 是后端成功状态，不是 `indexed`。

Nginx 配置位于 `nginx/default.conf`。其中使用 Docker 内部 DNS resolver 和变量形式的 `proxy_pass`，避免 API 容器重建后 Nginx 缓存旧容器 IP 而返回 `502`。

## 6. 正确配置原则

`.env` 至少保存本地运行所需的非提交配置，例如：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- 可选的 Embedding 模型配置

容器环境中的 `OPENAI_BASE_URL` 必须与实际使用的 OpenAI 兼容服务一致。Embedding 请求成功后，Worker 日志应依次出现：Embedding HTTP `200`、Qdrant collection/points 写入成功、Elasticsearch index/document 写入成功，最后任务返回 `status: ready`。

## 7. 验证方法

聚焦测试：

```powershell
python -m pytest tests/test_knowledge_base_api.py tests/test_celery_app.py tests/test_celery_indexing_task.py tests/test_indexing_task.py -q
```

静态检查：

```powershell
python -m ruff check knowledgeops
```

容器联调：

```powershell
docker compose ps
docker compose logs worker --tail 80
```

一次真实文档索引的成功证据是：

1. 前端上传接口返回 `201`。
2. 索引提交接口返回 `202`。
3. Worker 收到 `knowledgeops.index_document` 任务。
4. Embedding、Qdrant 和 Elasticsearch 请求均成功。
5. 任务结果包含 `status: ready` 与正确的 `chunk_count`。
6. 前端显示“索引状态：ready”。

## 8. 已知且可接受的提示

本地单元测试的 `AsyncQdrantClient(location=":memory:")` 会提示 payload index 在内存模式无效果。这是测试环境限制，不是生产缺陷。服务端 Qdrant 仍需要 payload index 用于按 `knowledge_base_id` 过滤，因此不得为消除 warning 删除 `knowledgeops/rag/vector_store.py` 中的相关代码。

## 9. 第六阶段结论

第六阶段完成后，系统具备可容器化运行的异步索引闭环和可操作的管理前端。文档从上传到 `ready` 的完整路径已经通过真实 Worker、Embedding 服务、Qdrant 和 Elasticsearch 验证。

后续第七阶段将在该稳定基础上增加 Neo4j GraphRAG、可观测性、评测页面和演示交付物。
