# 阶段 8：React + TypeScript 前端迁移与交付

## 用户问题

早期管理台用原生 HTML、CSS 与 JavaScript 组织。页面增多后，Agent、知识库、工单、通知和账户设置需要共享登录用户、导航状态和接口错误处理；继续依靠字符串选择器和全局脚本，容易出现按钮无响应、切页后状态不一致、一个脚本改动影响另一个页面的问题。

本阶段将运行中的前端迁移为 React + TypeScript。目标不是更换技术名词，而是让每个页面拥有清晰的组件边界、让接口返回值在编译期被检查，并保留原有 FastAPI 接口、Cookie 登录和权限隔离。

## 设计结论

| 决策 | 选择 | 原因 |
| --- | --- | --- |
| 页面框架 | React 18 | 用组件管理视图、局部状态和生命周期，避免手动拼接 DOM。 |
| 开发与构建 | Vite | 开发启动快，生产时产出纯静态文件，适合继续部署到 Nginx。 |
| 语言 | TypeScript | 登录用户、工单状态、知识库文档和 Agent 消息都有明确结构，类型能提前发现接口使用错误。 |
| 共享状态 | Zustand | 仅保存跨页面需要的登录用户、当前页面、导航目标、知识库缓存和提示信息；不把所有数据塞进全局状态。 |
| 图标 | Lucide React | 图标与按钮语义匹配，避免以文本按钮代替常见操作图标。 |
| API 边界 | 不改 FastAPI API | 请求仍经 `/api/v1`，浏览器仍用 HttpOnly Cookie 携带会话，后端仍负责权限判断。 |

## 前端结构

```text
knowledgeops/frontend/
├── src/
│   ├── api/                 # fetch 客户端、错误处理、接口类型
│   ├── components/          # 登录页、应用壳、可复用 UI
│   ├── pages/               # 工作台、Agent、知识库、工单、个人与管理页面
│   ├── store/               # Zustand 跨页面状态
│   ├── styles/              # React 专用布局和响应式样式
│   ├── App.tsx              # 认证启动与顶层分支
│   └── main.tsx             # React 挂载入口
├── package.json             # React、Vite、TypeScript 依赖与命令
├── vite.config.ts           # Vite 构建配置
└── Dockerfile               # Node 构建阶段 + Nginx 运行阶段
```

旧的静态页面与脚本暂时保留为迁移对照，但新的 `index.html` 只加载 `/src/main.tsx`。生产镜像只会服务 Vite 构建出的 `dist/`，因此旧脚本不会参与运行。

## 关键实现

### 1. 登录先于业务页面

`src/App.tsx` 启动时请求 `GET /api/v1/auth/me`：

- 成功：将用户写入 Zustand，渲染 `AppShell`。
- 返回 `401`：渲染登录/注册页。
- 退出登录：调用 `/auth/logout`，再清空前端用户状态，立即回到登录页。

这保证刷新页面后仍以服务端 Cookie 为准，而不是相信浏览器里一段可篡改的用户名文本。

### 2. 类型化接口与统一错误

`src/api/client.ts` 是唯一的基础请求入口。它自动添加 JSON 请求头、同源 Cookie，并把 FastAPI 的 `detail` 字段转换为可展示错误。`src/api/types.ts` 记录 `Ticket`、`KnowledgeDocument`、`AgentTurn`、`User` 等返回结构。

页面只关心业务：例如工单页面请求 `TicketPage`，详情页请求 `TicketDetail`。如果误把工单列表当作详情读取，TypeScript 会在构建前报错。

### 3. 共享导航状态，但不共享全部页面数据

`src/store/app-store.ts` 保存：

- `user`：当前经过服务端认证的用户；
- `activeView`：当前侧边栏页面；
- `routeTarget`：从工作台、通知或全局搜索打开的具体工单、会话、知识库或图谱实体；
- `knowledgeBases`：多个页面都会用到的知识库列表；
- `notice`：一次性成功、失败提示。

工单列表、Agent 消息、通知列表等仍保留在各自页面的局部状态中。这种划分避免全局状态变成难以维护的“数据仓库”。

### 4. 工单处理闭环

员工的“我的工单”页面支持筛选、搜索、查看活动时间线、补充信息、确认解决和重新打开。服务台的“待我处理”页面使用相同详情模型，但只向 `/service-desk/tickets/*` 发起领取、转派、请求补充、调优先级、升级与解决请求。

前端仅展示操作入口；后端通过当前 Cookie 用户的角色判断是否允许操作，并在服务层校验状态流转。因此用户不能仅靠修改浏览器按钮文字绕过权限。

### 5. 多阶段镜像

前端 Dockerfile 分为两个阶段：

```dockerfile
FROM node:20-alpine AS build
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html/
```

最终 Nginx 镜像不包含 `node_modules`、TypeScript 源码或 npm 下载缓存。`.dockerignore` 同时排除 `node_modules` 与 `dist`，让每次 Docker 构建只接收必要源码，并可复用 `npm ci` 的缓存层。

## 复现与验证

在项目根目录执行：

```powershell
Set-Location knowledgeops/frontend
npm ci
npm run check
npm run build
Set-Location ../..
docker compose build frontend
docker compose up -d --force-recreate --no-deps frontend
```

验证顺序：

1. 访问 `http://localhost:8080`，未登录时应出现登录页。
2. 登录后检查侧边栏；普通员工不应看到“待我处理”和“用户与权限”。
3. 创建一张工单，在“我的工单”补充信息；用服务台账号领取并解决；再由员工确认解决。
4. 在 Agent 中提问并对回答提交反馈；从工作台、通知或全局搜索打开目标工单和会话。
5. 创建知识库，分别上传本地文件、导入网页和添加文本，确认文档状态会更新。

## 常见问题

**页面空白**：先执行 `npm run check`，它能报告 TypeScript 导入、组件属性和 JSX 语法问题；再执行 `npm run build`。构建通过而容器仍显示旧页面时，通常是未执行前端镜像重建或浏览器缓存未刷新。

**Docker 构建找不到 `package-lock.json`**：先在 `knowledgeops/frontend` 执行一次 `npm install` 或 `npm ci`，确认锁文件已存在，再构建镜像。

**按钮显示但操作被拒绝**：检查当前登录账号的角色与工单状态。界面入口不是权限依据，服务端接口才是最终判断点。

**本地 `npm install` 没有权限写缓存**：可以临时指定项目内缓存，例如 `npm install --cache .npm-cache`；完成后删除该临时目录。不要为了安装依赖修改系统级 Node 或 npm 目录权限。

## 面试表达

“我把原生静态管理台迁移到 React + TypeScript + Vite。React 负责组件边界和生命周期，TypeScript 为工单、会话、知识库等 API 数据提供编译期约束，Zustand 只管理用户、导航和少量跨页面状态。后端 API 和 Cookie 鉴权没有迁移到前端，所有服务台权限与工单状态机仍由 FastAPI 校验。部署上使用 Node 构建、Nginx 运行的多阶段镜像，最终镜像不带源码依赖，前端改动也无需重建 Python API 镜像。”

## 历史记录

早期原生 HTML 片段拆分的记录仍保留在 `docs/` 根目录，便于理解迁移前的问题；本章描述的是当前运行版本的前端结构。
