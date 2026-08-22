# KnowledgeOps 离线测评 v0.4

v0.4 将评测从“检索和工具路由”扩展为四层证据：困难检索、多跳 RAG 回答、多轮建单 Agent、真实 API 安全门禁。

## 数据规模

| 内容 | 数量 | 目的 |
| --- | ---: | --- |
| Markdown 资料 | 160 | 40 个主题，每个主题包含现行制度、标准流程、例外流程、归档版本 |
| 困难检索题 | 800 | 每份资料 5 题，测试同主题流程区分、版本识别和边界判断 |
| 多跳问答题 | 160 | 120 题要求同时引用两份资料，40 题必须拒答 |
| Agent 工具调用题 | 100 | 普通对话、知识检索、工单读取、信息不足澄清、补全信息后的草稿生成 |
| 安全场景 | 32 | 对应确认、越权、审计、网页导入和文件导入的 API 集成测试 |

## 评测含义

1. 检索：比较 `vector`、`bm25`、`hybrid`、`hybrid_rerank` 的 Recall@5、MRR、nDCG@5 和 P95 延迟。
2. 多跳回答：固定使用 `hybrid_rerank` 取前 4 条资料，再让 Chat 模型回答。报告分别计算所需证据是否齐全、前 4 条证据精度、Gold 事实覆盖率、完整有依据回答率，以及无答案题的拒答率。
3. Agent：信息不足的建单请求必须不调用工具并要求补充信息；补全优先级、影响范围和持续时间后才应调用 `prepare_ticket_draft`。该调用只生成草稿，不写入工单。
4. Verifier：可选的独立模型根据题目、Gold 事实和回答输出 JSON 判定，并与确定性 Gold 规则评分比较一致率、误放行率和误拒绝率。它不回退使用 `CHAT_MODEL`，避免把自评伪装成独立审核。
5. 安全：使用临时 SQLite 数据库运行真实 FastAPI 接口，验证确认前零写入、确认后仅写入一次、跨员工访问隔离、服务台角色限制、审计保留及不安全网页导入拦截。

## 运行前准备

1. 创建知识库 `Evaluation v0.4`。
2. 导入 `docs/evaluation/fixtures-v0.4/` 下全部 160 个 Markdown 文件，等待全部状态变为 `ready`。
3. 记录该知识库 ID。
4. 配置 `CHAT_MODEL`、`CHAT_BASE_URL`、`CHAT_API_KEY`。完整 Verifier 测评还需配置不同模型或不同供应商的 `VERIFIER_MODEL`、`VERIFIER_BASE_URL`、`VERIFIER_API_KEY`。

## 主测评命令

```powershell
docker compose run --rm --no-deps -e PYTHONPATH=/app `
  -e QDRANT_COLLECTION=knowledgeops_chunks `
  -v "D:/Agent/CoreCoder:/app" api `
  python scripts/run_offline_evaluation.py `
  --dataset docs/evaluation/knowledgeops-gold-v0.4.json `
  --knowledge-base-id <v0.4知识库ID> `
  --methods vector,bm25,hybrid,hybrid_rerank `
  --run-verifier `
  --output-dir evaluation-results/v0.4
```

该命令不会创建工单。预计会执行约 2,400 次 Embedding 调用、约 260 次 Chat 调用和约 160 次 Verifier 调用；具体次数与失败重试策略相关，应以实际账单和日志为准。

## 安全与负载命令

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_evaluation_v04_security.py -q
```

```powershell
docker compose run --rm --no-deps -e PYTHONPATH=/app `
  -e QDRANT_COLLECTION=knowledgeops_chunks `
  -v "D:/Agent/CoreCoder:/app" api `
  python scripts/run_load_evaluation.py `
  --dataset docs/evaluation/knowledgeops-gold-v0.4.json `
  --knowledge-base-id <v0.4知识库ID> `
  --method hybrid_rerank `
  --concurrency 10,25,50 `
  --sample-size 100 `
  --output evaluation-results/v0.4/load.json
```

不要把合成 Gold 集结果表述为生产 SLA 或真实员工满意度。v0.4 的价值是让每项结论都可复跑、可定位到具体失败案例；生产前仍需使用脱敏日志和人工标注样本复验。
