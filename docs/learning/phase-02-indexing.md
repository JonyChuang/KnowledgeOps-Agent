# 阶段 2：知识库导入与异步索引

## 用户问题

员工上传一份文档后，系统不能只“保存文件”。它必须把内容变成能搜索、能引用、能反复处理的知识资产，同时不能让耗时的解析和模型调用阻塞浏览器请求。

## 阶段目标

- 支持文本、本地文件和公开网页三种导入入口。
- 解析 PDF、DOCX、Markdown、TXT、HTML 等资料并统一成文本。
- 将索引放进 Celery Worker，建立明确的文档状态机。
- 同步写入向量、关键词和图谱索引，为后续检索准备数据。

## 处理链路

```text
上传文件 / 网页地址 / 直接输入文本
  -> POST /knowledge-bases/{id}/documents...
  -> 保存 Document，状态 uploaded
  -> POST /documents/{id}/index
  -> Redis 投递 Celery 任务
  -> Worker 解析、分块、Embedding、写入索引
  -> ready 或 failed
```

`uploaded` 表示资料已经保存但还没开始处理；`indexing` 表示 Worker 已接手；只有所有必需索引写入成功才是 `ready`。任何关键步骤异常都应转为 `failed`，并保留可排查信息。

## 为什么使用异步任务

文件解析、Embedding 和外部存储网络调用的耗时不可预测。如果直接放在上传接口中，浏览器会长时间等待，反向代理可能超时，也无法看到进度。API 只做快速、可重试的状态提交；Worker 专注耗时计算，职责清晰。

## 关键文件

| 文件 | 阅读重点 |
| --- | --- |
| `knowledgeops/api/routers/knowledge_bases.py` | 文本、本地文件、网页导入和索引触发接口 |
| `knowledgeops/rag/parser.py` | 按文件后缀解析内容与大小限制 |
| `knowledgeops/rag/chunker.py` | 文档为什么要切成可召回的片段 |
| `knowledgeops/services/indexing.py` | 文档状态更新与索引编排 |
| `knowledgeops/tasks/celery_app.py`、`celery_indexing.py` | Celery 应用和任务入口 |
| `knowledgeops/tasks/indexing.py` | 生产环境中构造 Embedding、Qdrant、ES、Neo4j 客户端 |
| `tests/test_indexing_service.py`、`tests/test_celery_indexing_task.py` | 不依赖真实模型的验证方式 |

## 配置要点

- `EMBEDDING_MODEL`、`EMBEDDING_BASE_URL`、`EMBEDDING_API_KEY` 决定向量化服务。
- `EMBEDDING_DIMENSIONS` 必须与实际模型输出维度一致。
- `DOCUMENT_UPLOAD_MAX_BYTES` 和 `WEB_IMPORT_MAX_BYTES` 是输入保护，不应只依赖前端限制。
- `GRAPH_INDEXING_ENABLED=true` 时，索引任务还会连接 Neo4j。

## 最小复现

1. 按根目录 README 配置 `.env`，启动所有容器。
2. 注册并登录，在“知识库”创建“IT 支持资料库”。
3. 打开知识库，使用“添加文本”输入一段包含明确关键词的内容，例如 VPN 排障步骤。
4. 提交后观察文档状态；若停在 `indexing`，执行：

   ```powershell
   docker compose logs --tail 100 worker
   ```

5. 状态变为 `ready` 后，在 Agent 或全局搜索中输入文档中的关键词。

## 常见问题

- **文档永久停在 `indexing`**：通常是 Worker 未运行、Redis 不可达、Embedding 配置无效，或某个外部索引服务未就绪。
- **切换 Embedding 模型后报维度错误**：新旧向量维度混写到同一个 collection；应换 collection 或清理旧数据。
- **网页导入失败**：只支持可公开访问的 HTTP/HTTPS 页面，受下载大小与超时限制，不适合绕过登录页或内网权限。

## 面试表达

“文档上传和索引被拆成两个事务边界：API 负责保存元数据并投递任务，Worker 负责解析、切块和多索引写入。文档状态机让前端能显示真实进度，也让失败可以定位到异步任务，而不是把所有耗时工作塞进一个 HTTP 请求。”

## 历史记录

- [异步索引与容器化日志](../knowledgeops-learning-log-phase6.md)
