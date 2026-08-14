# KnowledgeOps Agent 学习路线

这套文档面向第一次接触企业 Agent 项目的学习者。阅读目标不是背诵框架名，而是能回答四个问题：用户为什么需要这个功能、后端怎样保证正确性、前端怎样与接口协作、改完后怎样证明它真的可用。

建议先完成根目录 [README](../../README.md) 的启动步骤，再按下面顺序阅读。每个阶段都可以独立复现，后一阶段只建立在前面已经理解的边界上。

| 阶段 | 主题 | 你会学到什么 | 建议验证 |
| --- | --- | --- | --- |
| 1 | [项目基础与领域建模](phase-01-foundation.md) | 分层架构、数据库模型、迁移和配置 | 模型与 API 基础测试 |
| 2 | [知识库导入与异步索引](phase-02-indexing.md) | 文件解析、Celery、文档状态机、向量写入 | 导入一篇资料并等待 `ready` |
| 3 | [混合检索与 GraphRAG](phase-03-retrieval-and-graphrag.md) | 向量召回、BM25、RRF、重排、图谱关联 | 对已索引资料执行检索 |
| 4 | [Agent 与 Function Calling](phase-04-agent.md) | 工具定义、受控写操作、多轮会话和降级 | 询问知识库、工单与建单草稿 |
| 5 | [工单协同与服务台](phase-05-ticket-collaboration.md) | 工单状态机、活动时间线、SLA 和角色边界 | 两个账号完成一次处理闭环 |
| 6 | [员工工作台与个人工作项](phase-06-workbench.md) | 工作台聚合、全局搜索、通知、收藏和反馈 | 验证导航与个人数据展示 |
| 7 | [登录、权限与数据隔离](phase-07-authentication.md) | Cookie 会话、角色授权、服务端数据范围 | 注册多个账号并切换角色 |
| 8 | [前端模块化与容器化排错](phase-08-frontend-and-delivery.md) | 静态片段加载、镜像更新、缓存和排错 | 重建前端并验证页面交互 |

## 阅读与动手方式

1. 先读每章的“用户问题”和“设计结论”，建立需求与实现之间的对应关系。
2. 再打开“关键文件”中列出的代码，沿着路由、服务、仓储和前端脚本阅读。
3. 执行“复现与验证”中的最小操作。不要一开始就运行所有测试。
4. 最后阅读“面试表达”，用自己的话复述设计取舍，而不是照着答案念。

## 旧日志说明

`docs/` 根目录中保留了早期逐次开发的详细记录，例如 `knowledgeops-learning-log-phase*.md` 和 `knowledgeops-learning-log.md`。它们是历史材料，阶段编号曾随需求调整而变化。新的学习路线以本目录为准，按最终功能边界重新编排；需要追溯某次具体实现时，再从各章末尾的“历史记录”链接进入。

## 通用验证命令

在项目根目录执行：

```powershell
python -m pytest -q
python -m ruff check knowledgeops tests
git diff --check
```

端到端验证依赖 Docker Compose。前端地址为 `http://localhost:8080`，健康检查为 `http://localhost:8080/health`。模型密钥只应保存在本地 `.env`，不要复制到学习日志、截图或 Git 提交中。
