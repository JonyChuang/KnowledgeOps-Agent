# 阶段 1：项目基础与领域建模

## 用户问题

企业里的资料、服务请求和处理记录通常散落在网盘、聊天和邮件中。项目首先要解决的不是“让模型回答”，而是把这些业务对象变成可追踪、可校验、可持久化的数据。

## 阶段目标

- 建立 FastAPI 应用、配置和健康检查。
- 用 SQLAlchemy 定义知识库、文档、用户、会话和工单等核心模型。
- 用 Alembic 把模型变更变成可重复执行的数据库迁移。
- 规定路由、服务、仓储和模型之间的职责边界。

## 设计结论

```text
浏览器 / API 调用
  -> Router：解析 HTTP、校验身份和参数
  -> Service：执行业务规则和状态流转
  -> Repository：读写数据库
  -> Model：定义持久化结构
```

这样做的好处是：前端不需要知道数据库细节；路由不会堆积业务逻辑；服务层可以被单元测试直接调用；以后更换存储实现时，影响范围较小。

## 核心对象

| 对象 | 解决的问题 | 关键关系 |
| --- | --- | --- |
| `KnowledgeBase` | 一组可共同检索的组织资料 | 一个知识库有多篇 `Document` |
| `Document` / `DocumentChunk` | 保存资料和可检索片段 | 一篇文档会被切成多个片段 |
| `User` / `AuthSession` | 登录身份与可撤销会话 | 一个用户可有多个会话记录 |
| `AgentConversation` / `AgentMessage` | 多轮 Agent 对话 | 对话和消息分表，便于列表摘要与详情加载 |
| `Ticket` / `TicketActivity` | 服务请求与处理时间线 | 一张工单对应多条活动记录 |
| `Notification` / `Favorite` / `RecentVisit` | 个人工作项 | 数据必须绑定当前用户 |

## 关键文件

| 文件 | 阅读重点 |
| --- | --- |
| `knowledgeops/config.py` | `Settings` 如何从 `.env` 读取配置，哪些值是密钥 |
| `knowledgeops/api/app.py` | FastAPI 生命周期、路由注册和数据库关闭 |
| `knowledgeops/models/` | ORM 模型与枚举状态 |
| `knowledgeops/repositories/` | 查询与持久化边界 |
| `knowledgeops/services/` | 业务规则和跨仓储编排 |
| `migrations/versions/` | 数据库迁移的演进顺序 |
| `tests/test_models.py`、`tests/test_migrations.py` | 如何验证模型和迁移 |

## 复现与验证

1. 阅读 `docker-compose.yml`，确认 PostgreSQL 是业务主库，Redis、Qdrant、Elasticsearch、Neo4j 分别用于不同职责。
2. 执行数据库迁移：

   ```powershell
   docker build --tag knowledgeops-agent:local .
   docker compose up -d postgres
   docker compose run --rm migrate
   ```

3. 验证基础代码：

   ```powershell
   python -m pytest tests/test_models.py tests/test_migrations.py tests/test_api.py -q
   ```

4. 启动完整系统后访问 `http://localhost:8080/health`，确认 API 能通过 Nginx 返回健康状态。

## 常见误区

- **把状态机放在前端。** 前端可以决定展示什么按钮，但不能决定状态是否允许改变；规则必须在服务端。
- **让路由直接操作 ORM。** 这样会导致同一业务规则在多个接口中复制，难以测试和维护。
- **只改模型不写迁移。** 本地 SQLite 可能看不出问题，但已有 PostgreSQL 数据库不会自动增加列或表。

## 面试表达

“我先把知识库、文档、会话和工单定义为独立领域对象。HTTP 路由只负责输入输出，服务层负责状态机和权限规则，仓储层负责持久化。这样 Agent、人工建单和服务台操作可以复用同一套业务约束，而不是各自直接改数据库。”

## 历史记录

- [早期项目总日志](../knowledgeops-learning-log.md)
- [认证与授权实现记录](../knowledgeops-learning-log-phase20-authentication.md)
