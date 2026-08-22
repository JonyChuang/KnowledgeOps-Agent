# KnowledgeOps 离线评测 v0.2

v0.2 是用于比较检索基线的困难 Gold 集。它不包含真实员工、客户、账号、凭据或生产系统资料，也不携带任何测评分数。

## 数据规模

| 内容 | 数量 | 目的 |
| --- | ---: | --- |
| Markdown 资料 | 24 | 为相近业务主题提供可混淆的证据来源 |
| 检索题 | 120 | 每份资料 5 条不同表达的问题 |
| Agent 工具选择题 | 24 | 验证聊天、知识库、工单查询和建单草稿的工具选择 |
| 安全门禁场景 | 12 | 列出必须由 API 或服务集成测试验证的安全不变量 |

检索资料覆盖网络、身份、事件、权限、终端和协作六类企业支持场景。每一类都包含相邻主题，例如“密码忘记”和“账号锁定”、“普通临时权限”和“破窗权限”，以避免模型只通过大类关键词得到正确答案。

## 五类检索题

每份资料对应以下五类题目，标签保存在 `category` 的冒号后：

| 题型 | 目标 |
| --- | --- |
| `direct` | 基础的流程或政策检索 |
| `paraphrase` | 员工自然语言、同义改写表达 |
| `contrast` | 与相邻主题的边界辨别 |
| `process` | 工单记录、责任或操作步骤 |
| `boundary` | 时效、范围、审批或权限边界 |

这并不包含“无答案题”。现有检索指标要求每个题目有至少一份正确证据；无答案能力需要单独引入拒答率和误召回率，不能错误地塞入 Recall/MRR/nDCG 的分母。

## 运行步骤

1. 在页面中创建新的知识库，例如 `Evaluation v0.2`。
2. 导入 `fixtures-v0.2/` 中全部 24 份 Markdown 文档，等待全部显示为“已就绪”。不要与 v0.1 的四份资料混在同一个知识库中。
3. 查询该知识库 ID。
4. 先运行 `vector,bm25`，确认索引、模型和端口连通，再运行完整对比。

在当前 Docker 网络配置和宿主机代理环境下，推荐使用一次性容器运行，`QDRANT_COLLECTION` 必须与 API/Worker 当前实际索引的集合一致：

```powershell
docker compose run --rm --no-deps -e PYTHONPATH=/app `
  -e QDRANT_COLLECTION=knowledgeops_chunks `
  -v "D:/Agent/CoreCoder:/app" api `
  python scripts/run_offline_evaluation.py `
  --dataset docs/evaluation/knowledgeops-gold-v0.2.json `
  --knowledge-base-id <知识库ID> `
  --methods vector,bm25,hybrid,hybrid_rerank `
  --skip-agent `
  --output-dir evaluation-results/v0.2
```

## 结果解释边界

v0.2 比 v0.1 更适合发现相邻流程混淆、关键词偏置和边界判断错误，但它仍是脱敏的合成企业支持资料，不能代替真实生产问答日志。报告必须同时给出每种方法的 Recall@5、MRR、nDCG@5、P50/P95 延迟，并按五类题型分析失败案例。

只有脚本在已导入的 v0.2 知识库上实际运行后生成的数字，才可以用于简历、答辩或面试表述。
