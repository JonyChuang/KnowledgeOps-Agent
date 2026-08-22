# 阶段 23：Qdrant 响应压缩兼容性排障

## 现象

在 Windows 宿主机运行离线评测时，Qdrant 客户端报出：

```text
zstd decompressor error: Allocation error : not enough memory
```

异常发生在读取集合配置的 HTTP 响应时，而不是模型生成向量或 Qdrant 执行相似度检索时。

## 排查结论

Qdrant 容器处于正常运行状态，内存占用很低，直接访问集合接口也能正常返回。因此这里的“not enough memory”不是向量库耗尽内存，而是 Windows 环境下 `httpx` 与 `zstd` 解码组合在处理压缩响应时的兼容性错误。

## 修复

创建 `AsyncQdrantClient` 时统一发送：

```python
headers={"Accept-Encoding": "identity"}
```

这会要求 Qdrant 返回未压缩响应。集合配置、检索结果等接口响应很小，开发环境中节省的压缩带宽可以忽略，却能避免本地解码失败。该设置不改变向量、余弦相似度、过滤条件或索引内容。

宿主机还可能遗留 SOCKS/HTTP 代理变量。Qdrant 默认地址是本机 `localhost`，不应该通过代理访问；因此 `qdrant_trust_env` 默认设为 `false`。只有远程 Qdrant 部署确实要求通过代理连接时，才在环境变量中显式设为 `true`。

## 运行提醒

新建的 24 份资料对应 `knowledgeops-gold-v0.2.json`，不能继续用 v0.1 的六题集。v0.2 评测应使用 Docker 一次性容器命令，以便同时复用容器内的模型网络、Qdrant 和 Elasticsearch；具体命令见 `docs/evaluation/V0_2_DESIGN.md`。

## 面试表达

“我区分了服务端资源耗尽和客户端协议兼容性问题：Qdrant 的容器内存与 API 响应都正常，错误出现在 Python 对 zstd 内容编码的解压阶段。我们通过在客户端明确协商未压缩响应，使协议行为稳定，同时不改变检索结果。”
