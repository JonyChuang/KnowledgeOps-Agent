# 阶段 3：混合检索与 GraphRAG

## 用户问题

只用向量检索时，精确的制度编号、产品名和报错码可能召回不稳定；只用关键词检索时，同义表达和自然语言提问又容易漏掉。企业资料还包含实体关系，例如“VPN 故障”和“网络访问规范”之间的关联。

## 阶段目标

- 并行执行 Qdrant 语义召回和 Elasticsearch BM25 召回。
- 用 RRF 融合不同检索器的排名，再执行可替换的重排。
- 保持 `knowledge_base_id` 在每一层的范围隔离。
- 将实体与片段关系写入 Neo4j，并提供 GraphRAG 查询入口。

## 混合检索链路

```text
用户查询
  -> Embedding 查询向量
  -> Qdrant 相似片段
  -> Elasticsearch BM25 关键词片段
  -> 按 chunk_id 去重并做 RRF 融合
  -> TokenOverlapReranker 重排
  -> 返回文本、来源、分数和引用位置
```

RRF 不直接相加“向量相似度”和“BM25 分数”，只根据每一路的排名贡献分数。因此两个检索器的分数尺度不同，也不会互相误导。`TokenOverlapReranker` 是可重复验证的确定性基线；未来可以替换为 Cross-Encoder 或供应商 Rerank 模型。

## GraphRAG 链路

```text
文档 Chunk
  -> RuleBasedEntityExtractor 抽取实体与关系
  -> Neo4j 图：实体 - 关系 - Chunk
  -> GraphRetriever 按查询实体找关联 Chunk
```

图谱检索不是用来替换 RAG，而是一个关系增强入口。当前规则抽取器便于本地复现，生产环境可在不改变 `GraphStore` 协议的前提下替换为模型抽取。

## 关键文件

| 文件 | 阅读重点 |
| --- | --- |
| `knowledgeops/rag/retriever.py`、`vector_store.py` | 语义检索和 Qdrant 适配 |
| `knowledgeops/rag/elasticsearch_keyword_store.py` | Elasticsearch 文本索引和 BM25 召回 |
| `knowledgeops/rag/fusion.py`、`hybrid_retriever.py` | RRF、候选规范化、并行召回与资源关闭 |
| `knowledgeops/rag/reranker.py` | 可替换的重排协议与基线实现 |
| `knowledgeops/graphrag/` | 实体抽取、Neo4j 存储、图谱检索 |
| `knowledgeops/api/routers/knowledge_bases.py` | `/search` 与 `/graph/search` 接口 |
| `knowledgeops/evaluation/` | Recall@k、MRR 与延迟评估 |

## 最小复现

1. 先完成阶段 2，确保至少一篇文档是 `ready`。
2. 在“图谱检索”选择该知识库，输入文档中出现的实体或关系词。
3. 使用 REST 接口验证混合检索：

   ```powershell
   Invoke-RestMethod `
     -Method Post `
     -Uri http://localhost:8080/api/v1/knowledge-bases/<知识库ID>/search `
     -ContentType 'application/json' `
     -Body '{"query":"VPN 无法连接如何处理","limit":5}'
   ```

4. 阅读返回结果中的 `chunk_id`、`sources` 和引用字段，确认结果不是没有来源的模型编造内容。
5. 运行聚焦测试：

   ```powershell
   python -m pytest tests/test_hybrid_retriever.py tests/test_graph_retriever.py tests/test_reranker.py -q
   ```

## 常见误区

- **把分数直接相加。** 不同召回器的评分没有可比性；应使用排名融合或经过标定的模型。
- **忘记知识库过滤。** 所有向量、关键词和图谱查询都必须带知识库范围，防止跨库泄露资料。
- **把图谱当作唯一真相。** 实体抽取会有误差，最终回答仍应保留原始文档片段引用。

## 面试表达

“我把检索拆为召回、融合和重排三个可替换阶段。Qdrant 和 BM25 并行召回，RRF 解决评分尺度不一致，重排器只处理候选集。GraphRAG 是关系增强，不替代原文证据；所有结果仍带文档片段引用，并在每层做知识库范围过滤。”

## 历史记录

- [GraphRAG 与前端集成日志](../knowledgeops-learning-log-phase7.md)
- [早期混合检索详细记录](../knowledgeops-learning-log.md)
