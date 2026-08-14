# KnowledgeOps Agent 学习日志（四）：第七阶段

本文记录 KnowledgeOps Agent 第七阶段的最终实现、运行方式和验证结果。第五、六阶段分别见 `docs/knowledgeops-learning-log-phase5-cn.md` 与 `docs/knowledgeops-learning-log-phase6.md`。本文仅记录最终可用的环境和实现，不记录历史依赖、证书或安装排错过程。

## 1. 阶段目标

第七阶段在第六阶段的异步索引和管理前端基础上，完成以下闭环：

1. 文档索引成功后写入 Neo4j 实体关系。
2. 通过实体关系查找关联文档块，形成 GraphRAG 检索能力。
3. 将第五阶段的 Agent API 接入管理前端。
4. 对知识问答、工单查询和人工确认建单进行端到端验证。
5. 完成容器联调、质量检查和最终交付文档。

## 2. 正确运行环境

- 仓库：`D:\Agent\CoreCoder`
- Conda 环境：`myagent`
- Python：`3.11.15`
- 容器运行时：Docker Desktop，WSL2 后端。
- Docker 数据目录：`D:\DockerData\DockerDesktopWSL`
- 前端地址：`http://localhost:8080`
- Neo4j Browser：`http://localhost:7474`
- API 前缀：`/api/v1`

敏感值只保存在本机 `.env` 中。交付文档只记录变量名称，不记录 API Key、数据库密码或 Neo4j 密码。

项目镜像由根目录手动构建：

```powershell
Set-Location D:\Agent\CoreCoder
conda activate myagent
docker build --tag knowledgeops-agent:local .
docker compose up -d
```

`docker-compose.yml` 中的应用服务引用 `knowledgeops-agent:local` 镜像，因此 `docker compose build` 的 `No services to build` 并不代表后端镜像已更新。

## 3. GraphRAG 设计

### 索引链路

```text
TextDocument
  -> DocumentChunk
  -> RuleBasedEntityExtractor
  -> GraphChunk -[:MENTIONS]-> GraphEntity
  -> Neo4j
```

正常文档索引仍然先完成 Embedding、Qdrant 和 Elasticsearch 的写入；图谱写入是索引成功路径的一部分。文档仅在所有必需索引步骤成功后才进入 `ready` 状态，失败则为 `failed`。

### 检索链路

```text
用户问题
  -> RuleBasedEntityExtractor
  -> 按 knowledge_base_id 过滤的 Neo4j 实体匹配和关系遍历
  -> GraphRetrievedChunk
  -> REST 响应或前端结果卡片
```

`knowledge_base_id` 仍然是数据隔离边界。它在图谱写入、查询和 API 路径中均被传递，避免不同知识库的图谱结果混合。

### 关键代码位置

| 文件 | 职责 |
| --- | --- |
| `knowledgeops/graphrag/models.py` | 图谱 chunk、实体和关系的数据模型。 |
| `knowledgeops/graphrag/store.py` | 图存储协议，隔离调用方与具体数据库。 |
| `knowledgeops/graphrag/neo4j_store.py` | Neo4j Cypher 写入、查询和资源关闭。 |
| `knowledgeops/graphrag/extractor.py` | 可复现的规则型实体抽取。 |
| `knowledgeops/graphrag/retriever.py` | 图谱检索编排，输出关联文档块。 |
| `knowledgeops/tasks/indexing.py` | 生产 Neo4j Store 工厂和索引集成。 |
| `knowledgeops/api/routers/knowledge_bases.py` | 图谱检索 REST 接口。 |

图谱检索接口：

```text
POST /api/v1/knowledge-bases/{knowledge_base_id}/graph/search
```

请求体沿用 `SearchRequest`，包含 `query` 和 `limit`；响应返回图谱关联的 chunk 标识、文档标识、来源文件名、序号和文本内容。

## 4. Agent 前端集成

第五阶段已经提供 Agent API；第七阶段将它接入 `knowledgeops/frontend/`。

| 文件 | 作用 |
| --- | --- |
| `knowledgeops/frontend/index.html` | Agent 对话和图谱检索页面结构。 |
| `knowledgeops/frontend/app.js` | 加载知识库选项、发起 Agent 请求、渲染引用、处理确认和取消。 |
| `knowledgeops/frontend/styles.css` | Agent 引用来源和确认操作的显示样式。 |
| `knowledgeops/api/routers/agents.py` | Agent 对话与确认接口。 |

前端使用同源相对地址 `const API_BASE = "/api/v1"`，请求会先到 Nginx，再代理到 FastAPI，不需要浏览器跨域配置。

### Agent 的安全边界

1. 知识问答可选择知识库并返回引用来源。
2. 工单查询只返回当前 `X-Actor` 所属的工单。
3. 创建工单请求先返回 `confirmation_required`，此时不产生写入。
4. 用户点击确认后，前端调用 `/agent/turns/{thread_id}/confirmation`，请求体为 `{ "approved": true }`。
5. 后端校验确认请求的 `X-Actor` 与初始对话的操作人一致，防止他人代为确认。

前端使用 DOM API 和 `textContent` 渲染响应及引用，不使用 `innerHTML` 拼接文档内容，避免把文档内容当作可执行页面代码。

## 5. 容器与反向代理

Compose 联调使用八个长期服务：

| 服务 | 责任 |
| --- | --- |
| `postgres` | 知识库、文档、工单、审计数据。 |
| `redis` | Celery broker 和结果后端。 |
| `qdrant` | 向量检索。 |
| `elasticsearch` | BM25 关键词检索。 |
| `neo4j` | 实体关系和图谱检索。 |
| `api` | FastAPI HTTP 服务。 |
| `worker` | Celery 异步索引任务。 |
| `frontend` | Nginx 静态前端和 API 反向代理。 |

一次性的 `migrate` 服务在应用启动前执行 Alembic 迁移，成功退出码为 `0` 是正常现象。Nginx 的 `/health` 代理到 `/api/v1/health`，因此下面命令可以同时验证前端代理和 API：

```powershell
Invoke-RestMethod http://localhost:8080/health
```

## 6. 最终验证结果

2026-08-11 的最终验收结果：

```text
python -m pytest -q
199 passed, 2 warnings

python -m ruff check knowledgeops tests
All checks passed!
```

同时确认：

```powershell
git diff --check
Invoke-RestMethod http://localhost:8080/health
docker compose ps
```

- `git diff --check` 未报告空白字符错误；Windows 下的 LF/CRLF 提示仅表示 Git 的行尾转换策略。
- 健康检查返回 `status: ok` 和 `service: knowledgeops-api`。
- API、Worker、前端、PostgreSQL、Redis、Qdrant、Elasticsearch 和 Neo4j 均处于运行状态。
- 已通过前端验证知识问答引用、图谱检索、工单查询，以及确认后创建工单。

当前两个 pytest warning 均为可接受的测试环境提示：Starlette TestClient 的第三方弃用提示，以及内存 Qdrant 的 payload index 提示。生产 Qdrant 仍需要 payload index，不应为消除本地 warning 删除生产索引逻辑。

## 7. 当前限制和后续方向

- `X-Actor` 是演示用身份标识。生产环境需接入真实认证、授权和审计策略。
- `MemorySaver` 只适用于单个 API 进程的待确认会话。重启服务或横向扩容前，应替换为持久化共享 checkpointer。
- 规则型实体抽取可复现且易于测试，但覆盖率有限。可以在不改变 `GraphStore` 和 `GraphRetriever` 接口的前提下，引入模型抽取器。
- 本地 Compose 的 Elasticsearch 关闭安全认证，仅适用于本地开发和演示。

第七阶段完成后，KnowledgeOps 已具备从文档上传、异步索引、混合检索、图谱检索到可控 Agent 工单协同的完整本地演示闭环。
