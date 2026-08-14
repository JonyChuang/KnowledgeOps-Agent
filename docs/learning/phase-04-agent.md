# 阶段 4：Agent、聊天模型与 Function Calling

## 用户问题

员工不会按照预设按钮逐项操作，他们会直接说“VPN 连不上”“查一下我的工单”“帮我建一个工单”。系统既要自然理解请求，又不能让模型越权读取数据或直接执行写操作。

## 阶段目标

- 保存多轮会话和消息，使刷新页面后可以恢复对话列表。
- 为 Chat 模型提供明确、受限的工具定义。
- 将“生成建单草稿”和“真正创建工单”拆成两步。
- 在模型不可用或不支持 Function Calling 时提供可解释降级。

## 工具调用链路

```text
用户消息 + 最近会话上下文
  -> OpenAI-compatible Chat Completions
  -> 模型选择工具或直接回答
  -> 服务端验证参数与当前用户权限
  -> 执行知识库检索 / 工单查询 / 草稿生成
  -> 模型根据工具结果组织中文回答
  -> 前端显示回答、引用或确认卡片
```

模型可见工具只有：

| 工具 | 作用 | 是否写数据 |
| --- | --- | --- |
| `search_knowledge_base` | 在当前选择的知识库检索资料 | 否 |
| `list_my_tickets` | 查询当前用户的工单 | 否 |
| `get_my_ticket_detail` | 查询属于当前用户的一张工单详情 | 否 |
| `prepare_ticket_draft` | 从描述中组织建单草稿 | 否 |

真正创建工单不在模型工具列表中。模型只能返回草稿，用户必须在界面明确确认后，服务端才调用 `TicketService` 写入数据。

## 为什么需要两个模型配置

- **Chat 模型**：负责自然语言理解、工具选择和回答生成，使用 `CHAT_*` 配置。
- **Embedding 模型**：负责把文档和查询变成向量，使用 `EMBEDDING_*` 配置。

两者职责不同，也可以使用不同供应商。缺少 Chat 配置时，项目会保留规则路由或明确提示模型不可用；缺少 Embedding 配置时，文档无法完成索引和检索。

## 关键文件

| 文件 | 阅读重点 |
| --- | --- |
| `knowledgeops/agents/function_calling.py` | OpenAI Function Calling 合约和工具 JSON Schema |
| `knowledgeops/agents/workflow.py` | LangGraph 工作流、暂停确认和错误分支 |
| `knowledgeops/agents/tools.py`、`ticket_tools.py` | 工具如何调用检索和工单服务 |
| `knowledgeops/agents/state.py` | 对话状态与消息结构 |
| `knowledgeops/services/conversation.py` | 对话、消息和摘要持久化 |
| `knowledgeops/tasks/agent.py` | 按请求构造模型、检索器和工具依赖 |
| `knowledgeops/api/routers/agents.py` | 对话轮次与确认接口 |
| `knowledgeops/frontend/agent.js` | 会话列表、消息渲染和确认交互 |

## 最小复现

1. 完成阶段 2，确保已有 `ready` 的资料，并在 `.env` 配置可用的 Chat 模型。
2. 在“智能助手”选择对应知识库，提问资料中的明确问题，检查回答是否附带引用。
3. 输入“查看我未关闭的工单”，确认只能返回当前登录用户的数据。
4. 输入“帮我创建一个无法连接企业 VPN 的工单”，检查先出现草稿与确认操作；取消后不应新增工单，确认后才应出现在“我的工单”。
5. 运行聚焦测试：

   ```powershell
   python -m pytest tests/test_agent_function_calling.py tests/test_agent_workflow.py tests/test_agent_chat.py -q
   ```

## 常见误区

- **把函数定义当作权限系统。** Function Calling 只约束模型如何提出请求；真正的权限检查必须在服务端工具和服务层执行。
- **让模型直接调用创建接口。** 模型可能误解指令或遗漏信息，高影响写操作必须增加人工确认。
- **无限保留会话上下文。** 上下文会增加成本并降低相关性；当前工作流只带最近有限消息。

## 面试表达

“我使用真实的 OpenAI 兼容 Function Calling，而不是关键词匹配假装 Agent。模型只能选择经过 JSON Schema 限制的读取工具和建单草稿工具；所有真实写入都要经过服务端权限校验和用户二次确认。即使模型行为异常，也不会直接创建或修改他人的数据。”

## 历史记录

- [Agent 工作流与确认建单日志](../knowledgeops-learning-log-phase5-cn.md)
- [会话持久化日志](../knowledgeops-learning-log-phase11-conversations.md)
- [Function Calling 日志](../knowledgeops-learning-log-phase19-function-calling.md)
