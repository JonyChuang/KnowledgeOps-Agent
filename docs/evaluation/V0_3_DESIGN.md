# KnowledgeOps 离线评测 v0.3

v0.3 是检索和 Chat Function Calling 的大规模脱敏评测集。它包含 100 份虚构企业支持资料、500 条检索题、100 条 Agent 工具选择题和 24 条安全门禁场景。

## 规模与分布

| 内容 | 数量 | 设计目的 |
| --- | ---: | --- |
| Markdown 资料 | 100 | 25 个业务主题，每个主题有策略、申请、异常、复核四类相近资料 |
| 检索题 | 500 | 每份资料 5 条题，覆盖直接、改写、边界、流程、时效 |
| Chat Function Calling 题 | 100 | 聊天、知识库检索、工单列表、工单详情、工单草稿 |
| 安全门禁场景 | 24 | 确认、越权、跨知识库、提示注入、导入和审计等场景 |

每个业务主题的四类文档共用部分背景，但分别描述标准策略、申请处理、异常响应与定期复核。这样可以检验系统是否只识别主题词，还是能分辨员工真正需要的流程。

## 运行前准备

1. 新建知识库 `Evaluation v0.3`，不要混入 v0.1/v0.2 文件。
2. 导入 `fixtures-v0.3/` 下全部 100 个 Markdown 文件，等待全部显示为 `ready`。
3. 查询这个新知识库的 ID。
4. 确认 `.env` 已配置可进行 OpenAI-compatible Function Calling 的 `CHAT_MODEL`、`CHAT_BASE_URL` 与 `CHAT_API_KEY`。

## 完整运行命令

以下命令**不含** `--skip-agent`，会同时运行 500 条检索评测与 100 条 Chat Function Calling 评测：

```powershell
docker compose run --rm --no-deps -e PYTHONPATH=/app `
  -e QDRANT_COLLECTION=knowledgeops_chunks `
  -v "D:/Agent/CoreCoder:/app" api `
  python scripts/run_offline_evaluation.py `
  --dataset docs/evaluation/knowledgeops-gold-v0.3.json `
  --knowledge-base-id <v0.3知识库ID> `
  --methods vector,bm25,hybrid,hybrid_rerank `
  --output-dir evaluation-results/v0.3
```

运行会调用约 1,500 次 Embedding 请求和 100 次 Chat 模型调用。应在网络稳定、模型额度充足时执行；中断时不要引用未写出 `report.md` 的中间结果。

## 报告解释

检索部分按 500 条问题报告 Recall@5、MRR、nDCG@5 与延迟。Agent 部分按 100 条问题报告工具精确选择率、参数 schema 合法率以及“建单只生成草稿、等待确认”的门禁率。

即使产生高分，v0.3 仍是脱敏合成资料。它比 v0.2 更适合观察规模、主题混淆与工具选择，但不能替代真实企业日志上的人工标注评测。
