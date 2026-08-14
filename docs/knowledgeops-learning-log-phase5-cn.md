# KnowledgeOps Agent 学习日志（二）：第五阶段

本文是第五阶段的中文学习记录。第一至第四阶段见 `docs/knowledgeops-learning-log.md`；第六阶段见 `docs/knowledgeops-learning-log-phase6.md`。

## 1. 正确开发环境

- 仓库：`D:\Agent\CoreCoder`
- Conda 环境：`myagent`
- Python：`3.11.15`
- 必须在终端显示 `(myagent)` 时运行项目命令。
- 依赖由 `pyproject.toml` 管理；API Key、密码等敏感值仅放在本地 `.env`，不提交、不截图、不写入日志。

常用命令：

```powershell
Set-Location D:\Agent\CoreCoder
conda activate myagent
python -m pytest -q
python -m ruff check knowledgeops
git diff --check
```

## 2. 阶段目标

第五阶段实现企业知识库 Agent 的完整基础工作流。它支持三类意图：

1. 知识库问答。
2. 查询当前操作人的工单。
3. 请求创建新工单。

工单创建是写操作，必须经过用户的第二次显式确认；问答和查询只能读取数据，不得产生写入。

## 3. 工作流

```text
POST /api/v1/agent/turns
  -> 请求级 AgentRuntime
  -> LangGraph 路由节点
  -> 知识问答 | 工单查询 | 工单草稿
  -> 创建工单前 interrupt 暂停

POST /api/v1/agent/turns/{thread_id}/confirmation
  -> 应用级共享 checkpointer
  -> 校验操作人和待确认状态
  -> Command(resume=True | False)
  -> 创建工单或取消
```

`AgentState` 只能保存可序列化的对话数据，例如用户消息、意图、操作人、待确认动作和响应内容。数据库会话、检索器、外部客户端等运行时对象不能写入 checkpoint。

## 4. 关键代码位置

| 模块 | 文件 | 职责 |
| --- | --- | --- |
| 状态与意图 | `knowledgeops/agents/state.py`、`router.py` | 定义可序列化状态、确认状态和确定性路由。 |
| Agent 工具 | `knowledgeops/agents/tools.py`、`ticket_tools.py` | 提供带引用的知识检索、工单查询和受保护的工单创建。 |
| 工作流 | `knowledgeops/agents/workflow.py` | 编排 LangGraph 节点、确认中断和恢复。 |
| 运行时工厂 | `knowledgeops/tasks/agent.py` | 创建请求级数据库与检索依赖；知识问答时才延迟创建检索器。 |
| 工单领域 | `models/ticket.py`、`schemas/ticket.py`、`repositories/ticket.py`、`services/ticket.py` | 保存工单、操作人边界和审计事件。 |
| HTTP API | `knowledgeops/api/routers/agents.py`、`knowledgeops/schemas/agent.py` | 提供 Agent 对话和确认接口。 |

## 5. API 契约

### 发起 Agent 对话

`POST /api/v1/agent/turns`

- 请求体：`user_message`，可选 `knowledge_base_id`。
- 当前开发阶段通过 `X-Actor` 请求头传入操作人。
- 响应包含：`thread_id`、状态、回答、引用、待确认动作、工单 ID 和错误信息。

### 确认或取消创建工单

`POST /api/v1/agent/turns/{thread_id}/confirmation`

- 请求体：`{ "approved": true }` 或 `{ "approved": false }`。
- 确认请求的 `X-Actor` 必须与最初对话一致。
- 不存在或非本人的对话返回 `404`；不存在待确认操作时返回 `409`。
- 对话状态包括：`completed`、`confirmation_required`、`cancelled`、`failed`。

## 6. 安全设计结论

1. 创建工单意图只生成 `PendingAction`，确认状态为 `PENDING`。
2. 确认节点通过 LangGraph `interrupt()` 暂停，暂停前绝不调用写入工具。
3. `ConfirmedTicketCreationTool` 还会独立校验 `AgentState.can_create_ticket`，避免绕过工作流直接写入。
4. FastAPI 应用状态持有共享 `MemorySaver`，使后续确认请求可恢复原线程。当前适合单进程开发环境；多实例部署应改用持久化共享 checkpointer。
5. 运行时工厂会在 `finally` 中关闭自身创建的检索器，工单路径不会无谓创建外部搜索客户端。

## 7. 验证结果

聚焦验证：

```powershell
python -m pytest tests/test_agent_api.py tests/test_agent_tools.py tests/test_agent_workflow.py -q
python -m ruff check knowledgeops/api knowledgeops/schemas
```

第五阶段完成后的全量回归基线：

```text
183 passed, 2 warnings
```

两条 warning 分别来自 Starlette TestClient 的第三方弃用提示，以及内存 Qdrant 的 payload-index 提示。后者是本地测试限制，生产 Qdrant 仍需要 payload index，不能删除相关代码。

## 8. 后续约束

- Agent 通过既有 `HybridRetriever` 进行只读检索；不要在 Agent 节点内重写向量召回、BM25、RRF 或重排。
- 任何新的写工具都应遵守“待确认动作 + 原操作人 + 显式确认”模式。
- 第六阶段的 Celery、前端和 Docker Compose 实现见 `docs/knowledgeops-learning-log-phase6.md`。
