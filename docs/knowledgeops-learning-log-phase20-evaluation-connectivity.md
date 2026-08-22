# 阶段 20：离线评测的检索服务连通性

## 本阶段解决的问题

Windows 宿主机运行离线评测时，向量检索返回 `502 Bad Gateway`。评测资料已经显示为“已就绪”，所以问题不在文档导入、文本切分或向量生成，而在评测进程到检索基础设施的网络连接。

## 根因

原先的 `qdrant` 和 `elasticsearch` 服务只存在于 Docker Compose 内部网络。API 和 Worker 可以用 `http://qdrant:6333`、`http://elasticsearch:9200` 访问；而从 Windows 启动的 Python 评测脚本不能解析这些 Docker 服务名。

宿主机的默认配置分别是 `http://localhost:6333` 和 `http://localhost:9200`，但 Compose 没有发布对应端口。因此 Qdrant 请求没有抵达向量库，最终表现为 502；即使修复向量检索，BM25 检索也会遇到相同问题。

## 设计与修复

为两个检索服务增加只绑定本机的端口映射：

```yaml
qdrant:
  ports:
    - "127.0.0.1:6333:6333"
elasticsearch:
  ports:
    - "127.0.0.1:9200:9200"
```

左侧 `127.0.0.1` 表示仅当前电脑可访问。这样本机评测脚本可以复用在线服务正在使用的同一份索引，同时不会把未鉴权的开发环境检索服务暴露给局域网。

重建容器只应用网络设置。Qdrant 索引保存在命名卷 `qdrant_data` 中，Elasticsearch 索引保存在 `elasticsearch_data` 中，因此不会丢失已导入的评测文档。

## 验证步骤

```powershell
docker compose up -d --force-recreate --no-deps qdrant elasticsearch
Invoke-RestMethod http://localhost:6333/collections
Invoke-RestMethod http://localhost:9200/_cluster/health
```

两个命令返回服务信息后，再运行检索评测。若端口被其他程序占用，Docker 会在重建命令中明确提示冲突。

## SOCKS 代理依赖

评测还要调用 Embedding 模型生成查询向量。如果终端设置了 `ALL_PROXY`、`HTTP_PROXY` 或 `HTTPS_PROXY` 为 SOCKS 地址，`httpx` 会自动读取该设置；但 SOCKS 传输层由可选依赖 `socksio` 提供。

本项目将 `socksio` 写入 `pyproject.toml`，因此新建虚拟环境或重建后端镜像都会自动安装。报错 `Using SOCKS proxy, but the 'socksio' package is not installed` 不是模型服务不可用，而是运行环境缺少网络传输依赖。

## 容器化运行的备用方案

当宿主机必须通过不可用的 SOCKS 代理访问模型服务时，可以让一次性容器执行评测。容器复用 Compose 内部网络，并将当前源码挂载到 `/app`：

```powershell
docker compose run --rm --no-deps -e PYTHONPATH=/app `
  -v "D:/Agent/CoreCoder:/app" api `
  python scripts/run_offline_evaluation.py `
  --dataset docs/evaluation/knowledgeops-gold-v0.1.json `
  --knowledge-base-id <知识库ID> `
  --methods vector,bm25,hybrid,hybrid_rerank `
  --skip-agent `
  --output-dir evaluation-results/v0.1
```

`--rm` 使评测容器结束后自动删除；索引和报告不在临时容器里，前者仍在 Docker 数据卷中，后者写入宿主机挂载的项目目录。

## 指标校验：nDCG 不得超过 1

本轮真实运行中曾出现 `nDCG@k > 1`。排查后发现，gold 集用 `source_name` 表示“文档证据”，而检索器返回“文档分块”；同一来源文档的重复分块被当作多条相关结果累加。

修复后，评测会先按 gold 集的证据标识去重，再计算 Recall、MRR 和 nDCG。标准化的 nDCG 上限为 1，超过 1 必须视为评测实现缺陷而不是性能优势。

## 集合配置一致性

本次还发现 `.env` 中配置的 `QDRANT_COLLECTION=knowledgeops_chunks_zhipu` 与当前 API/Worker 实际使用的默认集合 `knowledgeops_chunks` 不一致。原因是 Compose 的应用环境尚未把 `QDRANT_COLLECTION` 显式传给 API 和 Worker；已导入文档因此位于默认集合。

评测必须使用与实际应用相同的集合，否则 Qdrant 会按 `knowledge_base_id` 过滤出空结果，得到错误的 `vector = 0`。本轮真实报告通过一次性容器的 `-e QDRANT_COLLECTION=knowledgeops_chunks` 选择当前索引集合。

永久修复应分两步进行：先让 Compose 明确传入 `QDRANT_COLLECTION`，再把现有文档重新索引到最终确定的集合。不能直接切换 API 的集合名，因为旧集合中的文档会暂时无法被检索。这个变更应在确认目标集合后执行。

## 面试表达

“在线 API 与离线评测复用同一套向量索引和 BM25 索引，但运行在不同网络环境。容器内部通过 Docker 服务发现访问检索服务；本机评测通过只绑定 loopback 的端口映射访问。这个设计解决了可达性问题，也避免开发期检索服务被局域网误访问。”
