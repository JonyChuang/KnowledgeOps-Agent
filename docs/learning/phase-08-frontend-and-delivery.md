# 阶段 8：前端模块化、容器化与排错

## 用户问题

功能增加后，如果所有页面都堆在一个 HTML 或 JavaScript 文件中，导航、登录、知识库和工单模块会互相影响。另一方面，静态文件被复制进 Nginx 镜像后，修改代码却只刷新浏览器，会让人误以为“代码没有生效”。

## 阶段目标

- 将前端页面拆为可独立阅读的 HTML 片段与 JavaScript 模块。
- 让所有事件绑定在片段挂载完成后执行，避免错过 `DOMContentLoaded`。
- 明确前端与后端镜像的构建边界，减少无意义重建和磁盘增长。
- 为空白页、按钮无响应、旧缓存等问题建立固定排查顺序。

## 前端结构

```text
knowledgeops/frontend/
├── index.html                # 只保留壳和加载器
├── components-loader.js      # 获取 HTML 片段，按顺序加载脚本
├── components/               # 顶栏、侧栏、弹窗
├── views/                    # 工作台、知识库、工单、Agent、个人中心等页面
├── core.js                   # 统一启动、导航、认证和跨模块初始化
├── dashboard.js / tickets.js # 页面业务脚本
└── styles.css                # 样式
```

`components-loader.js` 先挂载全部 HTML 片段，再顺序加载 JavaScript，最后调用 `bootstrapFrontend()`。所有页面的 `bind...()` 函数由 `core.js` 统一调用，因此不会因为动态脚本错过浏览器的 `DOMContentLoaded` 事件。

## 镜像边界

| 修改内容 | 正确操作 | 不需要做什么 |
| --- | --- | --- |
| `knowledgeops/` Python、依赖、迁移 | 重建 `knowledgeops-agent:local`，重建 `migrate api worker` | 不需要重建前端 |
| `knowledgeops/frontend/` HTML、CSS、JS | `docker compose build frontend` 后重建 frontend 容器 | 不需要重建 API 镜像 |
| `nginx/default.conf` | 重建或重启 frontend 容器 | 不需要重建 Worker |
| 纯文档 | 不需要构建镜像 | 不需要重启任何容器 |

前端 Dockerfile 使用 `COPY . /usr/share/nginx/html/`。这意味着宿主机的代码不会自动挂载到运行中的前端容器，修改后必须构建新的前端镜像。

## 标准排错顺序

### 1. 页面空白

1. 用 `docker compose ps` 确认 frontend 容器运行。
2. 浏览器打开 `http://localhost:8080/health`，排除 API 不可达。
3. 打开浏览器开发者工具 Console，检查 `components-loader.js`、HTML 片段或模块脚本是否 404。
4. 执行前端重建命令后按 `Ctrl + F5`，排除旧脚本缓存。

### 2. 页面显示但按钮无响应

1. 确认目标元素具有正确的 `id` 或 `data-*` 属性。
2. 确认对应 `bind...()` 已由 `core.js` 启动流程调用。
3. 不要让动态加载脚本只依赖 `DOMContentLoaded`；该事件可能早于脚本加载完成。
4. 用 `node --check knowledgeops/frontend/<文件>.js` 排除语法错误。

### 3. 知识库列表空白

1. 先确认 `/api/v1/knowledge-bases` 请求是否返回数据或错误。
2. 再检查 `knowledge.js` 中的渲染函数和知识库下拉框同步函数是否存在。
3. API 失败时页面应展示错误提示，不能静默保留空容器。

## 最小验证

```powershell
Get-ChildItem knowledgeops\frontend -Recurse -File -Filter *.js | ForEach-Object {
  node --check $_.FullName
}

docker compose build frontend
docker compose up -d --force-recreate --no-deps frontend
```

重新打开管理台后，验证侧边栏导航、工作台快捷按钮、知识库列表、登录弹窗、头像下拉菜单和登出跳转。

## 面试表达

“前端没有继续维护一个超大的单页脚本，而是把页面片段和业务脚本拆开，再由启动器保证 DOM 挂载完成后统一初始化。这样可以避免动态加载场景下错过 DOMContentLoaded，也让知识库、工单、Agent 和认证模块各自有明确入口。容器层面我区分了前端静态镜像和后端 Python 镜像，避免每次样式修改都重建整个系统。”

## 历史记录

- [个人中心与前端拆分日志](../knowledgeops-learning-log-phase21-profile-and-frontend-structure.md)
- [Agent 交互体验日志](../knowledgeops-learning-log-phase12-agent-experience.md)
