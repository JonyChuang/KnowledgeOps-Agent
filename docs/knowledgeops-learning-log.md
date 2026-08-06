# KnowledgeOps Agent 开发与学习记录

本文档记录项目从 CoreCoder 向 KnowledgeOps Agent 演进的全过程。每个阶段均说明修改内容、设计原因、验证方式、问题与收获，方便其他开发者复现项目并理解每项技术决策。

## 项目目标

KnowledgeOps Agent 是面向企业内部知识库与工单协同场景的智能体应用。目标架构包括 FastAPI 服务、RAG 检索、业务工具调用、效果评测与容器化部署。

项目保留 CoreCoder 的 MIT 许可证与上游归属。原有 `corecoder/` 目录继续作为 CLI Coding Agent 的实现和参考；新增的企业业务代码统一放在 `knowledgeops/` 中。

## 开发约定

- 所有改造均在 `codex/knowledgeops-agent` 分支中进行。
- 每一项新功能至少应有一条聚焦的自动化测试。
- 原有 CoreCoder 测试属于回归测试，必须持续保持通过。
- 每完成一个阶段，记录修改文件、设计原因、验证命令、验证结果和待办事项。
- 日志中不得记录 API Key、数据库密码或真实业务文档内容；环境差异配置只保存在已被 Git 忽略的 `.env` 文件中。

---

## 阶段 1：FastAPI 服务骨架

**日期：** 2026-08-05  
**状态：** 已完成并验证

### 阶段目标

在不改写 CoreCoder 原有 Agent Loop 的前提下，建立一个最小可用的 HTTP 服务边界。该边界是后续知识库管理、RAG 检索、工单工具和前端管理台的接入点。

### 修改内容

| 文件 | 修改内容 | 在项目中的作用 |
| --- | --- | --- |
| `pyproject.toml` | 增加 `fastapi`、`uvicorn[standard]`、`pydantic-settings`；将 `knowledgeops` 加入构建包；开发依赖增加 `httpx`；注册 `knowledgeops-api` 命令。 | 让服务端依赖可以被项目声明和安装，并提供统一启动命令。`httpx` 是 FastAPI 测试客户端所需依赖。 |
| `README.md` | 新建项目说明和上游归属说明。 | `pyproject.toml` 将其声明为构建元数据；缺失该文件会导致 Hatchling 无法生成包元数据。 |
| `knowledgeops/__init__.py` | 新建 KnowledgeOps 应用包。 | 将企业业务代码与原有 CLI Coding Agent 隔离，避免后续功能耦合。 |
| `knowledgeops/config.py` | 新增 `Settings` 与 `get_settings()`。 | 集中读取 `.env`，并统一管理应用名称、API 前缀、CORS 和后续数据库/模型配置。 |
| `knowledgeops/api.py` | 新增 FastAPI 应用工厂、CORS 中间件和 `GET /api/v1/health`。 | `create_app()` 便于后续注入测试配置；健康检查用于本地验证、容器探针和前端服务状态判断。 |
| `knowledgeops/main.py` | 新增 Uvicorn 启动入口。 | 支持通过 `knowledgeops-api` 启动服务，无需记忆模块路径。 |
| `tests/test_api.py` | 新增健康检查集成测试。 | 验证应用工厂能正确构建应用，并返回第一个真实 HTTP 接口。 |
| `tests/test_core.py` | 工具数预期从 7 更新为 9；默认配置测试切换到 `tmp_path`。 | `now` 和 `fetch_url` 已经注册为工具；临时目录可避免项目 `.env` 影响“源码默认值”测试。 |
| `tests/test_tools.py` | 工具数预期从 7 更新为 9。 | 使旧测试与当前工具注册表一致。 |

### 设计决策

第一阶段刻意不接入数据库、LLM 调用和 RAG 流程。先让最小服务可独立测试，可以把后续问题拆分为基础设施、API、检索或模型调用问题，而不是把所有错误混在一起排查。

`knowledgeops/` 被设计为与 `corecoder/` 并行的应用包，而不是直接重写原包。这样既保留了原 Agent 的可运行参考，也能依靠原测试集及时发现改造造成的回归问题。

### 遇到的问题与解决方式

1. **可编辑安装失败，提示 `README.md` 不存在。**
   - 原因：当前分支曾删除 README，但 `pyproject.toml` 的 `readme = "README.md"` 仍是构建元数据的一部分。
   - 解决：新建 KnowledgeOps 项目 README，并保留上游归属说明。

2. **默认模型配置测试读取了本地 `.env`。**
   - 原因：`Config.from_env()` 会自动查找并加载项目根目录的 `.env`，本地的 `CORECODER_MODEL=gpt-5.6` 覆盖了源码默认值 `gpt-5.5`。
   - 解决：测试使用 `monkeypatch.chdir(tmp_path)` 在临时目录中运行，以测试无环境文件干预时的真实默认值。

3. **工具数测试过期。**
   - 原因：当前工具注册表已有 9 个工具，但旧测试仍断言为 7。
   - 解决：同步更新测试预期值，并保留该断言作为工具注册变化的提醒。

### 验证方式

在 Python 3.10+ 环境中逐条执行：

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m uvicorn knowledgeops.api:app --reload
```

健康检查接口：

```text
GET http://127.0.0.1:8000/api/v1/health
```

预期响应：

```json
{"status":"ok","service":"knowledgeops-api"}
```

### 验证结果

- 可编辑安装成功。
- Uvicorn 成功启动，健康检查接口返回 HTTP 200。
- 2026-08-05 使用项目 `myagent` 环境执行测试：`90 passed in 19.07s`。
- `git diff --check` 通过，未发现空白字符错误。

### 本阶段收获

1. `pyproject.toml` 的 `readme` 字段属于构建元数据，引用文件必须存在，即使只进行本地开发。
2. 对环境变量驱动的配置做测试时，既要清理进程环境变量，也要隔离 `.env` 文件发现路径。
3. 新服务从第一个端点开始就应具备 API 级测试，而不应只依赖“Uvicorn 能启动”的人工验证。

### 下一阶段

接入异步持久化层：以 PostgreSQL 为部署目标，以 SQLite 作为本地和测试回退；首先实现知识库、文档、文档处理状态和审计事件等领域实体。

---

## 阶段 2：异步数据层、知识库 API 与数据库迁移

**日期：** 2026-08-06  
**状态：** SQLite 路径已完成并验证；PostgreSQL 容器验收待第 6 天完成

### 阶段目标

为 KnowledgeOps Agent 建立可演进的数据基础：用户能够创建知识库、上传文本型文档，并查询文档的处理状态。系统还需要为后续 RAG 索引、工单协同和审计追踪保留稳定的数据边界。

本阶段使用 **SQLAlchemy 异步 ORM** 访问数据库，使用 **Alembic** 管理数据库结构版本。开发和自动化测试使用无需额外服务的 SQLite；未来 Docker Compose 部署会通过环境变量切换到 PostgreSQL。这样既降低本地学习门槛，也避免把 SQLite 的开发便利性误当成生产方案。

### 修改内容

| 文件或目录 | 修改内容 | 在项目中的作用 | 为什么需要这样修改 |
| --- | --- | --- | --- |
| `pyproject.toml` | 增加 `sqlalchemy[asyncio]`、`aiosqlite`、`asyncpg` 和 `alembic` 依赖。 | 声明异步 ORM、SQLite 驱动、PostgreSQL 驱动和迁移工具。 | 依赖必须在项目元数据中声明，其他开发者执行安装命令后才能得到同样的运行环境。`asyncpg` 虽然当前尚未连接 PostgreSQL，但它是未来容器部署时 SQLAlchemy 异步连接 PostgreSQL 所必需的驱动。 |
| `knowledgeops/config.py` | 增加 `database_url` 和 `auto_create_schema` 配置项。默认 URL 指向本地 SQLite。 | 将数据库地址和建表策略从业务代码中抽离，统一由环境配置控制。 | 同一份代码必须能在本地、测试和容器中运行。通过 `DATABASE_URL` 覆盖配置后，无需修改 Python 源码即可切换到 PostgreSQL。 |
| `knowledgeops/db.py` | 新增 `Database` 类、异步 Engine、会话工厂、会话生成器、建表与释放连接方法。 | API 请求和未来的后台任务都通过它获取独立数据库会话。 | 连接池和会话生命周期是基础设施职责，不应散落在路由函数中。每个请求独享一个 `AsyncSession`，可避免并发请求共享事务或连接状态。 |
| `knowledgeops/models/base.py` | 新增 ORM 基类、UUID 字符串主键和创建/更新时间混入类。 | 为所有领域表提供一致的主键和审计时间字段。 | 统一基础字段可减少重复代码；UUID 适合 API 暴露和分布式场景，避免递增整数 ID 被外部轻易枚举。 |
| `knowledgeops/models/knowledge.py` | 新增 `KnowledgeBase`、`Document` 和 `DocumentStatus`。文档状态包含 `uploaded`、`indexing`、`ready`、`failed`。 | 保存知识库、原始文档和后续索引任务的生命周期状态。 | 第 3 天的解析、切分与向量化是异步耗时工作。显式状态使前端和 API 能准确说明文档是刚上传、正在索引、已可检索还是处理失败。 |
| `knowledgeops/models/audit.py` | 新增 `AuditEvent` 模型。 | 记录创建知识库和上传文档等关键业务动作。 | 企业知识库中的写操作需要可追溯性。审计事件保存操作者、事件类型、关联实体和安全的元数据，但不保存原始文档内容。 |
| `knowledgeops/models/__init__.py` | 集中导出模型，并确保 `Base.metadata` 注册所有表。 | 同时服务于应用运行和 Alembic 自动发现模型。 | 如果某个模型没有被导入，Alembic 可能看不到对应的表，导致生成的迁移不完整。 |
| `knowledgeops/repositories/knowledge.py` | 新增知识库、文档和审计事件 Repository。 | 封装查询和持久化细节，向 Service 提供面向业务的读取/写入方法。 | 路由层不应该直接拼接 SQL 或承担查询规则；Repository 让数据访问逻辑集中，也便于未来替换或优化查询。 |
| `knowledgeops/services/knowledge.py` | 新增 `KnowledgeService`、资源不存在/冲突异常、知识库创建与文本上传业务流程。上传时计算 SHA-256 校验和，并写入审计事件。 | 协调多个 Repository、事务提交与业务约束。 | “创建文档”不是单次插入：它还要验证父知识库存在、避免同一知识库内重复内容、记录审计事件，并在失败时回滚事务。将这些规则放在 Service 中可以保证 API、CLI 或后续任务调用时行为一致。 |
| `knowledgeops/schemas/knowledge.py` | 新增创建请求和读取响应的 Pydantic Schema。 | 定义 HTTP 输入/输出的数据契约，避免把 ORM 对象和数据库字段直接暴露给客户端。 | Schema 能在请求进入业务层前校验字段，也让 API 文档、测试和前端都有稳定的接口定义。 |
| `knowledgeops/api/dependencies.py` | 新增获取请求级数据库会话的依赖。 | FastAPI 路由通过 `Depends` 获得会话。 | FastAPI 负责在请求完成后关闭会话，路由函数无需手工管理连接，从而避免连接泄漏。 |
| `knowledgeops/api/routers/knowledge_bases.py` | 新增创建/查询知识库、上传/查询文档和查询单个文档状态的 REST 端点；暂用 `X-Actor` 请求头标识操作者。 | 为 Swagger、前端管理台和后续工作流提供真实的知识库管理 API。 | 路由层只做协议转换：请求校验、依赖注入，以及将业务异常转换为 HTTP 404/409。临时 `X-Actor` 为审计链路提供可验证输入，后续身份认证接入后会替换为真实用户身份。 |
| `knowledgeops/api/app.py` 与 `knowledgeops/api/__init__.py` | 将原单文件 API 重构为应用工厂、依赖和路由包。 | 让 API 随功能增长仍保持清晰的模块边界。 | 将所有端点放在一个文件会快速变得难以维护。按路由领域拆分后，知识库、对话、工单等模块可独立演进。 |
| `alembic.ini`、`migrations/env.py` | 初始化 Alembic 并配置异步迁移环境。 | `alembic upgrade head` 能根据环境变量连接 SQLite 或 PostgreSQL，并按顺序执行迁移。 | `Base.metadata.create_all()` 适合本地快速启动，却不能追踪已部署数据库如何逐步升级。生产环境必须用可审查、可复现的迁移脚本管理结构变化。 |
| `migrations/versions/72b32edaa199_create_knowledgeops_tables.py` | 生成首个迁移，创建 `knowledge_bases`、`documents`、`audit_events` 表、索引与唯一约束。 | 为一个全新数据库建立初始版本的完整结构，并支持 `downgrade()` 回退。 | 文档的 `(knowledge_base_id, checksum)` 唯一约束是重复上传防线；状态、知识库 ID 和审计字段上的索引为后续按状态处理、按知识库查询和追踪事件提供基础性能保障。 |
| `tests/test_database.py`、`tests/test_models.py`、`tests/test_repositories.py`、`tests/test_knowledge_service.py`、`tests/test_schemas.py` | 新增数据库、模型、Repository、Service 和 Schema 的聚焦测试。 | 从底层连接到业务规则分层验证数据能力。 | 分层测试能更快定位错误：模型错误无需等到 API 测试才发现，业务规则也不需要依赖浏览器或真实网络请求才能验证。 |
| `tests/test_knowledge_base_api.py` | 新增知识库和文档 API 集成测试。 | 验证路由、依赖注入、Service 和数据库能连成完整调用链。 | 单元测试无法确认 HTTP 状态码、请求字段和响应结构是否匹配；该测试覆盖客户端实际使用的接口行为。 |
| `tests/test_migrations.py` | 新增从空 SQLite 文件运行 `python -m alembic upgrade head` 的自动化测试，并检查迁移版本表及三个业务表。 | 将一次性的手工迁移验证固化为每次回归测试都会运行的质量门禁。 | 它通过子进程调用与部署相同的 Alembic 命令，并使用临时数据库，确保测试不会被本地已有 `knowledgeops.db` 的表结构掩盖。 |
| `.gitignore` | 忽略本地 SQLite 文件。 | 防止开发数据库和迁移测试临时产物进入版本库。 | 数据库结构应由迁移脚本管理；个人本地数据不应作为源码提交，也不应污染其他开发者的测试。 |

### 核心调用链

```text
HTTP 请求
  -> FastAPI Router（校验请求、映射 HTTP 异常）
  -> KnowledgeService（业务规则、事务、审计）
  -> Repository（数据访问）
  -> AsyncSession / SQLAlchemy
  -> SQLite（本地与测试）或 PostgreSQL（容器部署）
```

以“上传文本型文档”为例：路由接收 `knowledge_base_id`、文件名和文本内容；Service 先确认知识库存在，再对内容计算 SHA-256 校验和；Repository 创建状态为 `uploaded` 的文档；Service 同一事务内写入 `document.uploaded` 审计事件并提交。第 3 天的索引任务会从 `uploaded` 状态接手，把状态推进为 `indexing`，成功后变成 `ready`，失败则写为 `failed` 并记录错误原因。

### 设计决策

1. **开发与测试使用 SQLite，部署目标使用 PostgreSQL。**
   - SQLite 不需要启动额外服务，适合初学者、本地调试和每次 CI 测试；PostgreSQL 更适合生产并发、连接池和后续复杂查询。两者都通过 SQLAlchemy 异步 URL 接入，减少环境切换时的应用代码差异。

2. **把 `create_schema()` 限定为本地/测试便利能力，生产以 Alembic 为准。**
   - 自动建表不能描述“已有数据库如何升级”。生产容器将关闭 `AUTO_CREATE_SCHEMA`，先运行 `alembic upgrade head`，从而让每次结构变化都有版本记录和审查入口。

3. **文档先保存原文与状态，不在上传请求中立即完成 RAG 索引。**
   - 解析 PDF、切分文本和调用 Embedding 模型都可能耗时或失败。将上传和索引拆开，可让用户立刻获得上传响应，并在第 3/6 天由后台任务可靠地推进索引状态。

4. **用数据库唯一约束作为重复内容的最终防线。**
   - Service 计算 SHA-256 是为了在同一知识库内检测相同内容；数据库的唯一约束则保证即使两个请求并发到达，也不会产生重复文档。应用层提示和数据库约束共同保障正确性。

5. **审计事件记录元数据而非文档正文。**
   - 审计需要回答“谁在何时做了什么”，但原文可能包含内部信息。事件中只保存文件名、类型和校验和，既能追踪操作，也降低敏感内容扩散风险。

### Alembic 工作方式

Alembic 把数据库结构当作一份按时间排序的代码历史：

1. 修改 SQLAlchemy 模型后，使用 `python -m alembic revision --autogenerate -m "描述本次变化"` 生成候选迁移。
2. 人工检查生成文件，尤其确认表、索引、约束和 `downgrade()` 是否符合预期。
3. 使用 `python -m alembic upgrade head` 将尚未执行的迁移应用到当前数据库。
4. 使用 `python -m alembic current` 查看当前数据库已处于哪个迁移版本。

本阶段执行 `current` 的结果为 `72b32edaa199 (head)`。它表示当前 SQLite 数据库已成功应用首个迁移，且该迁移就是代码仓库中的最新版本。`revision --autogenerate` 只生成迁移 Python 文件，不会修改数据库；真正修改数据库的是 `upgrade head`。

### 验证方式

在已安装项目依赖的 Python 环境中执行：

```powershell
# 查看当前数据库所处的迁移版本。
python -m alembic current

# 仅验证迁移能从空数据库创建所有表。
python -m pytest tests/test_migrations.py -q

# 运行 CoreCoder 回归测试与 KnowledgeOps 全部测试。
python -m pytest -q
```

### 验证结果

- 已在新的临时 SQLite 数据库上手工执行 `python -m alembic upgrade head`，随后 `python -m alembic current` 输出：`72b32edaa199 (head)`。
- `python -m pytest tests/test_migrations.py -q`：`1 passed in 1.44s`。
- `python -m pytest -q`：`101 passed in 15.94s`。
- 测试覆盖了既有 CoreCoder 回归测试与本阶段新增的数据库、模型、Repository、Service、Schema、API、迁移测试；未发现回归。

### 当前边界与待办事项

- **已验证：** SQLite 异步连接、SQLite 建表、SQLite Alembic 迁移、知识库/文本型文档 API、业务规则和完整 Python 测试套件。
- **尚未验证：** 真实 PostgreSQL 容器上的 Alembic 迁移与 API 连接。这不是遗漏的测试结论，而是第 6 天 Docker Compose 环境尚未创建，因此必须如实保留为待验收项。
- **下一阶段：** 实现 Markdown/PDF 解析、文本切分、Embedding、Qdrant 索引与文档状态流转。完成后，`uploaded` 文档才能变为可被检索的 `ready` 文档。

### 本阶段收获

1. 数据库代码的核心不只是“把对象存进去”，还包括连接生命周期、事务边界、唯一约束、错误映射和可追溯审计。
2. SQLAlchemy 模型描述的是目标结构，Alembic 迁移描述的是从旧结构走到目标结构的过程；两者都需要纳入版本控制。
3. 自动化迁移测试必须从空数据库开始，否则已有本地表可能让错误迁移看起来“能够运行”。
4. 将 API、Service、Repository 和模型分层后，后续接入异步索引任务、LangGraph 工具和工单模块时，可以复用同一套业务规则而不复制数据库代码。

---

## 阶段 3：文档解析、切分与向量索引

**日期：** 2026-08-06  
**状态：** 进行中，第一小步已验证

### 阶段目标

把第二阶段保存的“整篇原始文档”加工成 RAG 检索可以使用的知识片段：先统一不同来源的文本格式，再切分为带位置和来源信息的 Chunk，之后生成 Embedding 并写入 Qdrant。最终用户提问时，系统能够返回相关片段和来源，而不是让大模型凭空回答。

本阶段采用小步实现：先完成不依赖外部服务的解析和切分，再增加数据库 Chunk 记录，最后接入 Embedding 与 Qdrant。每一步都有独立测试，便于第一次开发项目的用户理解数据是如何逐层流动的。

### 第一小步：文档标准化与文本切分

| 文件或目录 | 修改内容 | 在项目中的作用 | 为什么需要这样修改 |
| --- | --- | --- | --- |
| `knowledgeops/rag/__init__.py` | 新增 RAG 包，并统一导出解析和切分函数。 | 为后续解析器、Embedding、向量检索提供稳定的模块入口。 | 调用方只依赖 `knowledgeops.rag`，不需要知道具体实现文件；后续替换切分算法时可以减少调用方改动。 |
| `knowledgeops/rag/parser.py` | 新增 `ParsedDocument`、`infer_source_type()` 和 `parse_text_document()`；统一换行符、去除首尾空白，并拒绝空文档。 | 把原始文本转换为后续 RAG 处理统一使用的对象。 | 文档可能来自 Windows、Linux、Markdown 或未来的 PDF。解析层把来源差异隔离起来，让切分器只处理标准化文本。空文档没有可检索内容，应在进入索引队列前失败。 |
| `knowledgeops/rag/chunker.py` | 新增 `TextChunk` 和基于字符窗口的 `split_text()`；支持 `chunk_size` 与 `overlap` 参数。 | 将长文档拆成可独立向量化和召回的小片段，并保留字符起止位置。 | Embedding 模型和向量检索不适合直接处理整篇超长文档。片段重叠可以减少句子在边界处被截断造成的上下文丢失；字符窗口是当前 MVP 的简单实现，后续可升级为按 token 或 Markdown 段落切分。 |
| `tests/test_rag.py` | 新增换行标准化、空文档拒绝、重叠切分和非法参数测试。 | 验证 RAG 输入加工的核心规则。 | 这些测试不需要数据库、模型 API 或 Qdrant，执行快速，能够在接入外部服务前先固定纯逻辑行为。 |

### 第一小步的调用逻辑

```text
Document.content（数据库中的原文）
  -> parse_text_document()
  -> ParsedDocument（统一文本 + 来源类型 + 元数据）
  -> split_text()
  -> list[TextChunk]（片段文本 + 顺序 + 字符位置）
```

例如，`chunk_size=800`、`overlap=120` 时，下一片段会从上一片段结束位置向前回退 120 个字符。这样每个片段可以单独生成向量，同时相邻片段仍保留一部分上下文。`chunk_index` 保证检索结果可以恢复原文顺序，`start_char` 和 `end_char` 为以后展示引用位置提供依据。

### 第一小步的设计边界

- 当前只实现文本和 Markdown 的统一处理，尚未实现真正的 PDF 解析。
- 当前按字符切分，不等价于模型 token 数；这是为了先跑通业务链路，后续会根据实际模型升级。
- 当前 Chunk 只存在于内存中，还没有数据库表和向量 ID；下一小步会补上持久化模型。

### 第一小步验证结果

- `python -m pytest tests/test_rag.py -q`：`4 passed in 0.06s`。
- `python -m pytest -q`：`105 passed in 16.18s`。
- 第二阶段的数据库、API、迁移测试和原 CoreCoder 回归测试均保持通过。

### 下一小步

新增 `DocumentChunk` ORM 模型和 Alembic 迁移，让每个 Chunk 与原始 `Document` 建立一对多关系，并保存片段顺序、文本、字符位置及未来的向量库 ID。完成后，索引任务即使进程重启，也能从数据库恢复处理进度。

### 第二小步：Chunk 持久化与迁移治理

| 文件或目录 | 修改内容 | 在项目中的作用 | 为什么需要这样修改 |
| --- | --- | --- | --- |
| `knowledgeops/models/chunk.py` | 新增 `DocumentChunk` ORM 模型，保存原文所属文档、片段顺序、文本、字符位置、`vector_id` 和 `embedding_model`。 | 将内存中的 `TextChunk` 转变为可恢复、可查询的业务数据。 | 仅在内存中切分的结果会随进程结束而丢失，也无法把关系数据库中的来源信息与 Qdrant 中的向量点关联。关系数据库保存文本和处理事实，Qdrant 将在后续保存高维向量。 |
| `knowledgeops/models/knowledge.py` | 在 `Document` 上新增 `chunks` 一对多关系，并配置 `delete-orphan` 级联删除。 | 使一篇原文可以拥有多个有序 Chunk；删除文档时同步删除派生片段。 | Chunk 没有脱离原始文档而独立存在的业务含义。级联删除避免遗留无来源的片段记录和错误引用。 |
| `knowledgeops/models/__init__.py` | 导出 `DocumentChunk`。 | 使应用代码和 Alembic 都能注册该模型。 | Alembic 只能比较已经加入 `Base.metadata` 的表；遗漏导入会造成“代码有模型但迁移没有表”的隐蔽问题。 |
| `tests/test_chunks.py` | 新增 Chunk 与 Document 的 SQLite 持久化测试。 | 验证外键关联、字段保存和新会话读取。 | 不只验证对象能创建，还要验证事务提交后数据仍存在，并且默认未索引 Chunk 的 `vector_id` 为 `None`。 |
| `migrations/versions/47e70d53e3bf_add_document_chunks.py` | 从初始迁移 `72b32edaa199` 派生，创建 `document_chunks` 表、外键、唯一约束和两个索引。 | 为已部署/已存在的数据库提供可重复执行的结构升级路径。 | `(document_id, chunk_index)` 唯一约束保证同一文档不能出现两个相同顺序的片段；`document_id` 索引支持按文档读取片段，`vector_id` 索引支持从向量检索结果回查业务数据。 |
| `tests/test_migrations.py` | 将 `document_chunks` 加入全新数据库迁移验收表集合。 | 验证任意空 SQLite 数据库执行 `alembic upgrade head` 都会得到四张业务表。 | 本地已经存在表时，错误迁移可能被掩盖；该测试始终使用临时数据库，能真实验证完整迁移链。 |
| `knowledgeops/config.py` | 将 `auto_create_schema` 默认值改为 `False`，并明确 Alembic 是持久化结构的唯一来源。 | 禁止正常启动的 FastAPI 服务绕过迁移脚本直接创建表。 | `create_all()` 不会记录 Alembic 版本。若自动建表和 Alembic 混用，就会产生“表已存在，但迁移历史为空”的冲突。测试仍显式设置为 `True`，所以临时 SQLite 测试不需要手工跑迁移。 |
| `tests/test_config.py` | 新增默认关闭自动建表的配置测试。 | 固定本次迁移治理规则，防止默认值被误改回 `True`。 | 这是一次由真实问题驱动的回归测试：将来修改配置时，测试会提醒开发者不能再让应用启动自动改变持久化数据库结构。 |

### 遇到的问题与解决方式

1. **Alembic 生成第二份迁移时提示 `Target database is not up to date`。**
   - 原因：本地 `knowledgeops.db` 之前被 FastAPI 生命周期中的 `Base.metadata.create_all()` 自动创建了 `audit_events`、`knowledge_bases` 和 `documents` 表，但没有 `alembic_version` 记录。Alembic 因此无法确认数据库处于初始迁移版本。
   - 表现：执行 `python -m alembic upgrade head` 时，初始迁移尝试再次创建 `audit_events`，得到 `sqlite3.OperationalError: table audit_events already exists`。
   - 解决：先复制本地 SQLite 文件作为可恢复备份，再运行 `python -m alembic stamp 72b32edaa199`。`stamp` 只写入迁移版本记录，不执行建表 SQL；它适用于“现有结构已经等同于某个迁移版本，但历史记录缺失”的场景。

2. **自动建表与迁移管理职责冲突。**
   - 原因：`create_all()` 适合隔离测试或极简原型，却不具备迁移历史、版本审查和升级路径；持久化开发数据库继续默认开启它会破坏 Alembic 的前提。
   - 解决：默认关闭 `auto_create_schema`，由 Alembic 执行结构升级；测试夹具则针对临时 SQLite 文件显式开启它，以保持测试快速且相互隔离。

### 第二小步验证结果

- 已执行 `python -m alembic stamp 72b32edaa199`，将已有初始表结构登记到迁移历史中。
- 已执行 `python -m alembic revision --autogenerate -m "add document chunks"`，仅检测到预期的 `document_chunks` 表和两个索引。
- 已执行 `python -m alembic upgrade head`，`python -m alembic current` 输出：`47e70d53e3bf (head)`。
- `python -m pytest tests/test_chunks.py tests/test_migrations.py tests/test_config.py -q`：`3 passed in 2.36s`。
- `python -m pytest -q`：`107 passed in 16.59s`。

### 第三小步：Chunk Repository 与索引准备服务

| 文件或目录 | 修改内容 | 在项目中的作用 | 为什么需要这样修改 |
| --- | --- | --- | --- |
| `knowledgeops/repositories/chunk.py` | 新增 `DocumentChunkRepository`，提供按文档查询 Chunk 和“删除旧 Chunk 后写入新 Chunk”的方法。 | 封装 `document_chunks` 表的读写规则。 | 重复索引同一文档时，旧 Chunk 必须被整体替换，不能和新 Chunk 混在一起。Repository 不提交事务，使 Service 可以把 Chunk、文档状态和审计事件作为一次原子业务操作提交。 |
| `knowledgeops/repositories/__init__.py` | 导出 `DocumentChunkRepository`。 | 为 Service 提供统一的 Repository 导入入口。 | 调用方不需要了解 Repository 的具体文件路径，模块边界更清晰。 |
| `knowledgeops/services/indexing.py` | 新增 `DocumentIndexingService.prepare_document_chunks()`。该方法读取原文、调用解析器和切分器、构造 ORM Chunk、持久化数据、更新文档状态与 `chunk_count`，并记录审计事件。 | 把多个技术步骤编排成一条可重复执行的业务流程。 | 路由、后台任务或未来 Celery Worker 都应调用同一个 Service。这样无论由谁触发索引，都会使用相同的状态、事务和审计规则。 |
| `knowledgeops/services/__init__.py` | 导出 `DocumentIndexingService`。 | 让其他业务模块通过 `knowledgeops.services` 使用索引服务。 | 对外暴露层稳定后，内部文件重组不会影响调用代码。 |
| `tests/test_indexing_service.py` | 新增端到端服务测试，使用 900 字符文档验证两个 Chunk、重叠起始位置、文档状态和审计事件。 | 验证解析、切分、Repository、数据库、状态更新和审计记录已真正连成调用链。 | 单独的解析或模型测试无法保证业务步骤按照正确顺序协作。该测试还使用新的数据库会话读取数据，确认提交后的持久化结果真实存在。 |

### 第三小步的调用逻辑

```text
uploaded Document
  -> DocumentIndexingService.prepare_document_chunks()
  -> parse_text_document() 统一原文格式
  -> split_text() 生成带重叠的 TextChunk
  -> DocumentChunkRepository.replace_for_document()
  -> 保存 DocumentChunk 记录
  -> Document.chunk_count 更新为片段数量
  -> 写入 document.chunked 审计事件
  -> Document.status 保持为 indexing
```

这里刻意没有把状态更新为 `ready`。`ready` 的业务含义是“可以被用户检索”，而当前 Chunk 还没有生成 Embedding，也没有写入 Qdrant。`indexing` 表示该文档已经进入索引流水线；只有下一步向量写入成功后才能变成 `ready`。如果解析器收到无效内容，服务会把状态改为 `failed` 并记录错误信息，使现有文档状态 API 能够向客户端暴露失败原因。

### 第三小步验证结果

- `python -m pytest tests/test_indexing_service.py -q`：`1 passed in 1.75s`。
- `python -m pytest -q`：`108 passed in 17.58s`。
- 新测试确认 900 个字符按照 `chunk_size=800`、`overlap=120` 被切为两个 Chunk；第二个 Chunk 的 `start_char` 为 `680`，与重叠规则一致。

### 第四小步：Embedding Provider 抽象

| 文件或目录 | 修改内容 | 在项目中的作用 | 为什么需要这样修改 |
| --- | --- | --- | --- |
| `knowledgeops/rag/embeddings.py` | 新增 `EmbeddingProvider` 协议和 `DeterministicEmbeddingProvider` 本地实现。 | 规定“输入有序文本，输出等顺序向量”的统一契约，并提供不联网的测试实现。 | 业务代码不应绑定某一家模型 SDK。通过接口隔离后，可以在测试中使用确定性实现，在部署中替换为 OpenAI 等真实 Provider，而不改动索引流程。 |
| `knowledgeops/rag/__init__.py` | 导出 Embedding Provider 协议和确定性实现。 | 让 RAG 模块对外提供统一导入入口。 | 索引服务和测试只依赖公开入口，内部文件位置变化不会扩散到调用方。 |
| `tests/test_embeddings.py` | 新增稳定性、批量输入顺序和非法维度测试。 | 验证本地 Provider 的基础契约。 | 测试重点不是向量语义质量，而是保证相同文本产生相同维度的结果、输出顺序不改变，并防止配置超过 SHA-256 能提供的 32 个字节。 |

### 第四小步的设计边界

`DeterministicEmbeddingProvider` 使用 SHA-256 摘要将文本映射为浮点数。它**不是**语义 Embedding，不能用于真实知识检索效果评估；它只用于本地开发和自动化测试，使项目在没有 API Key、没有网络连接和没有向量服务时仍能验证完整的数据流。

真实 Provider 将实现同一个 `EmbeddingProvider` 协议。这样后续索引服务不需要知道向量来自本地测试实现还是 OpenAI API，只需依赖 `embed_texts()` 返回的有序向量列表。

### 第四小步验证结果

- `python -m pytest tests/test_embeddings.py -q`：`3 passed in 0.07s`。
- `python -m pytest -q`：`111 passed in 17.22s`。
- 已验证同一文本的向量稳定、批量输入输出保持顺序，以及无效维度在构造 Provider 时被拒绝。

### 下一小步

根据 OpenAI 官方 SDK 文档实现真实 Embedding Provider，并保持 API Key 只从环境变量读取、不写入代码或学习日志。之后会接入 Qdrant 向量库，把 `DocumentChunk`、Embedding 和 `vector_id` 串成可检索索引。

---

## 一周交付计划

**目标：** 在七天内交付可部署、可评测、可现场演示的 KnowledgeOps Agent。V2 加分项必须形成真实调用链，不能只在依赖清单中出现。

| 天数 | 当日交付物 | 主要修改位置 | 当日验收标准 |
| --- | --- | --- | --- |
| 第 1 天 | FastAPI 服务骨架 | `knowledgeops/config.py`、`knowledgeops/api.py`、`tests/test_api.py` | `GET /api/v1/health` 返回 200；全量测试通过。 |
| 第 2 天 | 异步数据层与知识库 API | `knowledgeops/db.py`、`models/`、`repositories/`、`services/`、`api/routers/`、Alembic 迁移 | 可以创建知识库、上传文本型文档、查询文档状态；PostgreSQL 和 SQLite 测试均通过。 |
| 第 3 天 | 文档解析、切分、Embedding 与 Qdrant 索引 | `knowledgeops/rag/`、`tasks/indexing.py`、文档状态模型 | 导入 Markdown/PDF 后生成 Chunk，写入 Qdrant，能返回相似片段及来源信息。 |
| 第 4 天 | 混合检索、Rerank 与基础评测 | `rag/retriever.py`、`rag/reranker.py`、`evaluation/`、Elasticsearch 配置 | BM25 和向量召回经 RRF 融合，Rerank 生效；输出 Recall@5、MRR 和检索耗时。 |
| 第 5 天 | LangGraph 工作流与工单协同 | `knowledgeops/agents/`、`tools/`、`tickets/`、审计模型 | 对话可在“知识库问答、查工单、建工单、人工确认”之间路由；回答带引用，写操作需确认。 |
| 第 6 天 | 异步任务、前端管理台与容器化 | `Celery` 任务、`web/`、`docker-compose.yml` | 可在前端上传文档、发起对话、确认建单；Docker Compose 可启动 API、Worker、PostgreSQL、Redis、Qdrant、Elasticsearch 和前端。 |
| 第 7 天 | V2：Neo4j 图谱增强、可观测性、演示与文档 | `graphrag/`、`observability/`、`examples/`、`README.md` | 图谱检索可作为可选召回策略运行；评测页和调用 Trace 可查看；全量测试、演示数据、架构图和 3 分钟演示流程齐备。 |

### V2 范围约束

- Elasticsearch 必须负责关键词/BM25 召回，Qdrant 必须负责向量召回，两者通过 RRF 融合；不能只启动容器而不接入检索链路。
- Neo4j 只做“实体 - 文档 - 工单”关系增强和可选 GraphRAG 召回，不在第一周实现复杂长期记忆系统。
- Celery 只负责耗时的解析、Embedding、索引和批量评测；在线对话不经过任务队列。
- 多 Agent 不列入第一周核心范围。单 Agent 的路由、工具权限、引用和评测完整可用，比不稳定的多 Agent 更有招聘说服力。

---

## 后续阶段模板

```md
## 阶段 N：<阶段名称>

**日期：** YYYY-MM-DD  
**状态：** 计划中 | 开发中 | 已验证

### 阶段目标

### 修改内容

### 设计决策

### 遇到的问题与解决方式

### 验证方式

### 验证结果

### 本阶段收获

### 下一阶段
```
