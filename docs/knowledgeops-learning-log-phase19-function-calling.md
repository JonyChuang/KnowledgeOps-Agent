# 阶段 19 学习日志：原生 LLM Function Calling Agent

## 1. 要解决的问题

早期 Agent 通过“意图分类 -> 固定工作流分支”执行功能。即使使用了 Chat 模型，模型也只负责猜测 `knowledge_qa`、`ticket_query` 或 `ticket_create`，真正能走到哪条路径由程序预先决定。这种方式安全、容易测试，但自然语言表达稍有变化就可能路由失败，无法体现真实 Agent 的工具决策能力。

本阶段将核心改为 **LLM Function Calling**：模型看到用户消息、历史上下文和服务端声明的工具后，自行决定是否、以及调用哪一个工具。服务端始终保留执行权和数据权限控制。

## 2. 执行链路

```text
用户消息 + 最近 8 条持久化上下文
  -> Chat 模型（tools / tool_choice=auto）
  -> 模型返回 tool_calls 或普通文本
  -> 服务端校验参数、执行允许的工具
  -> 将结果作为 role=tool 消息回传模型
  -> 模型生成面向员工的最终回答
```

单轮最多允许 3 次模型工具决策，避免异常模型反复请求工具造成无限循环。

实现采用 OpenAI 兼容的 Chat Completions `tools` / `tool_calls` 协议，而不是仅用模型输出 JSON 做意图分类。依据官方 OpenAI 文档，Function Calling 是由应用定义带参数约束的自定义函数、模型选择是否调用、应用执行后将结果交回模型的模式。[OpenAI Tools Guide](https://developers.openai.com/api/docs/guides/tools)

## 3. 模型可见的工具

| 工具 | 作用 | 服务端边界 |
| --- | --- | --- |
| `search_knowledge_base` | 检索当前选择的知识库 | 必须存在 `knowledge_base_id`；只返回引用片段。 |
| `list_my_tickets` | 查看当前员工工单 | 强制使用当前 `actor`，不能传入其他员工。 |
| `get_my_ticket_detail` | 查看一张个人工单详情 | 仍以当前 `actor` 查询，不能借 ID 越权读取。 |
| `prepare_ticket_draft` | 整理建单草稿 | 只产生草稿，不写数据库。 |

每个工具都声明 `strict: true` 和 `additionalProperties: false`。这会要求支持该协议的模型按 JSON Schema 输出参数；无论模型是否遵守，服务端还会做长度、枚举和值范围校验。

## 4. 为什么不把 create_ticket 直接交给模型

模型没有 `create_ticket` 工具，只有 `prepare_ticket_draft`。草稿一旦准备好，LangGraph 将状态转入 `confirmation_required` 并中断。只有员工在页面点击“确认创建工单”后，原有的受控创建节点才可以写数据库。

这让 Function Calling 与人工审批结合：模型负责理解自然语言和准备结构化参数，人负责批准外部副作用，服务端负责最终权限与数据校验。

## 5. 兼容性与降级

应用仍保留旧的规则路由和基础 Chat 回答作为降级路径：当 `.env` 未配置完整的 `CHAT_MODEL`、`CHAT_BASE_URL`、`CHAT_API_KEY` 时，不会尝试工具调用。对于已经配置模型但模型服务不支持 OpenAI Function Calling 的情况，页面会提示检查模型服务的 Function Calling 支持，而不是默默退回关键词逻辑。

## 6. 测试证据

新增 `tests/test_agent_function_calling.py`，覆盖：

1. 模型请求 `list_my_tickets` 后，后端以当前员工身份执行，再以 `role=tool` 回传结果并获得最终回复。
2. 模型请求知识库搜索后，引用会随最终回答保留给前端展示。
3. 模型请求 `prepare_ticket_draft` 后，会进入人工确认节点；确认前不存在创建动作。
4. OpenAI 兼容客户端请求携带 `tools`、`tool_choice=auto`、`parallel_tool_calls=false`，并可解析返回的 `tool_calls`。

## 7. 面试表达

> 我将 Agent 从意图分类驱动的固定分支，升级为 LLM 原生 Function Calling。模型只负责决定是否使用哪一个受限业务工具，服务端负责执行、参数校验和数据权限隔离，再把工具结果回传给模型生成最终回答。涉及写操作时，我没有直接暴露建单函数，而是只提供草稿工具并用 LangGraph interrupt 做人工确认。因此它既有真实 Agent 的自主工具决策能力，也保留了企业系统必须具备的最小权限和审批边界。
