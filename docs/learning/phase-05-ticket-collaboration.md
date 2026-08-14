# 阶段 5：工单协同与服务台

## 用户问题

知识库能回答“应该怎么做”，但它不能替代处理过程。真实企业还需要记录谁提出了问题、谁在处理、何时请求补充、结果是什么，以及员工是否确认问题已解决。

## 阶段目标

- 用标准字段建立服务请求，减少描述缺失和重复建单。
- 建立后端控制的工单状态机与活动时间线。
- 区分员工、服务台和管理员的操作边界。
- 支持领取、转派、补充、优先级调整、升级、解决、确认关闭和重开。

## 状态机

```text
员工创建
  -> open（待受理）
  -> in_progress（处理中）
  -> awaiting_requester（待申请人补充）
  -> resolved（已解决）
  -> closed（已关闭）

closed / resolved
  -> reopen（重新打开，必须填写原因）
```

状态不是一个前端颜色标签。服务端会检查当前状态、操作人的角色和必填原因，再决定是否允许流转；每次有效操作都会生成 `TicketActivity`，时间线才能解释“为什么变成这个状态”。

## 角色边界

| 操作 | 员工 | 服务台 | 管理员 |
| --- | --- | --- | --- |
| 创建、查看自己的工单、补充信息 | 是 | 是 | 是 |
| 确认解决、重开自己的工单 | 是 | 是 | 是 |
| 查看待处理队列、领取工单 | 否 | 是 | 是 |
| 转派、调优先级、升级、标记解决 | 否 | 是 | 是 |
| 调整用户角色 | 否 | 否 | 是 |

## 为什么活动表独立存在

只在 `Ticket` 表中保存“当前状态”无法回答“谁在什么时候把优先级从中改成高”。独立的活动表保存状态变化、评论、转派、补充请求和解决说明；它既是详情页时间线的数据源，也是以后 SLA、审计和通知的触发来源。

## 关键文件

| 文件 | 阅读重点 |
| --- | --- |
| `knowledgeops/models/ticket.py` | 工单、活动、状态和优先级枚举 |
| `knowledgeops/services/ticket.py` | 状态机、SLA、权限检查和活动写入 |
| `knowledgeops/api/routers/tickets.py` | 员工侧接口 |
| `knowledgeops/api/routers/service_desk.py` | 服务台队列和处理接口 |
| `knowledgeops/schemas/ticket.py` | 请求与响应契约 |
| `knowledgeops/frontend/create-ticket.js` | 标准化建单与相似建议 |
| `knowledgeops/frontend/tickets.js` | 我的工单、详情抽屉、服务台操作 |
| `tests/test_ticket_service.py`、`tests/test_service_desk_api.py` | 业务规则与权限验证 |

## 最小复现

1. 用管理员账号注册第二个账号，并在“用户与权限”中将它设为 `service_desk`。
2. 用员工账号创建“无法连接企业 VPN”的工单，填写影响范围和优先级。
3. 用服务台账号进入“待我处理”，领取工单并请求补充信息。
4. 切回员工账号补充信息；再切回服务台账号标记解决。
5. 员工确认关闭，检查活动时间线是否完整记录每一步。
6. 运行聚焦测试：

   ```powershell
   python -m pytest tests/test_ticket_api.py tests/test_ticket_service.py tests/test_service_desk_api.py -q
   ```

## 常见误区

- **前端直接修改状态。** 这会绕开角色判断、原因校验、活动记录和通知生成。
- **所有人看全部工单。** 员工侧必须按当前用户过滤；服务台队列也必须通过角色限制。
- **只有状态没有处理说明。** “已解决”如果没有解决说明，员工无法判断是否真的可验证。

## 面试表达

“工单模块的核心不是 CRUD，而是服务端状态机。员工、服务台和管理员走同一套业务服务，但权限和允许的状态转换不同。每次处理动作会写入活动时间线，使通知、SLA 和审计有统一的数据来源。”

## 历史记录

- [我的工单日志](../knowledgeops-learning-log-phase9-tickets.md)
- [工单协同日志](../knowledgeops-learning-log-phase13-ticket-collaboration.md)
- [状态流转日志](../knowledgeops-learning-log-phase14-ticket-workflow.md)
- [待我处理日志](../knowledgeops-learning-log-phase15-service-desk.md)
