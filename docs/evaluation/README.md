# KnowledgeOps 离线评测 v0.1

本目录用于保存可复现的评测资料，不保存真实员工文档、账号、API Key 或自动生成的分数。

## 评测组成

- `fixtures/`：可安全导入演示知识库的脱敏资料。
- `knowledgeops-gold-v0.1.json`：版本化 gold 集，包含检索题、Function Calling 用例和安全门禁场景。
- `evaluation-results/`：每次本地运行生成的 Markdown/JSON 报告，默认被 Git 忽略。

## 首次运行

1. 在网页中创建一个知识库，例如“Evaluation v0.1”。
2. 将 `fixtures/` 中的四份 Markdown 文档导入该知识库，并等待它们全部成为 `ready`。
3. 获取知识库 ID：

```powershell
docker compose exec postgres psql -U knowledgeops -d knowledgeops -c "select id, name from knowledge_bases;"
```

4. 在项目根目录运行：

```powershell
.\.venv\Scripts\python.exe scripts\run_offline_evaluation.py `
  --dataset docs\evaluation\knowledgeops-gold-v0.1.json `
  --knowledge-base-id <上一步的知识库ID> `
  --output-dir evaluation-results\v0.1
```

默认会依次评估 `vector`、`bm25`、`hybrid`、`hybrid_rerank`、`graph`，并对 Chat 模型做 Function Calling 工具选择评测。`graph` 需要 Neo4j 图谱索引已开启；尚未准备时可先运行：

```powershell
.\.venv\Scripts\python.exe scripts\run_offline_evaluation.py `
  --dataset docs\evaluation\knowledgeops-gold-v0.1.json `
  --knowledge-base-id <知识库ID> `
  --methods vector,bm25,hybrid,hybrid_rerank `
  --skip-agent `
  --output-dir evaluation-results\retrieval-v0.1
```

移除 `--skip-agent` 后，需要 `.env` 中配置支持 OpenAI Chat Completions Function Calling 的 `CHAT_MODEL`、`CHAT_BASE_URL` 与 `CHAT_API_KEY`。该评测只让模型选择工具和生成参数，不会查询工单、更不会创建工单。

## 结果如何解释

- `Recall@k`：正确证据是否在前 k 条中出现。
- `MRR`：第一条正确证据排得是否靠前。
- `nDCG@k`：多条相关证据的整体排序质量。
- `P50/P95 latency`：典型请求和较慢请求的检索耗时。
- `Exact tool selection`：模型选中的工具是否与 gold 集预期完全一致。
- `Valid arguments`：模型给出的 Function Calling 参数是否符合工具 JSON Schema。
- `Confirmation draft guard`：建单请求是否只产生草稿、等待用户确认。

安全用例属于零容忍门禁：未确认写入、跨员工读取、无服务台角色操作均必须为零。它们由 API 与工作流集成测试验证，不能用平均分掩盖失败。

报告中的 `TBD` 表示尚未运行，绝不代表零分或已达标。只有脚本在实际模型、索引和知识库上运行后写出的数字，才能在 README、答辩或面试中引用。
