# 阶段 7：登录、权限与数据隔离

## 用户问题

早期演示可以用 `anonymous` 或请求头模拟操作人，但这不能满足真实平台需求：刷新后身份不可靠，用户能伪造名字，也无法保证会话、工单和通知真正隔离。

## 阶段目标

- 支持注册、登录、登出、个人资料修改和密码修改。
- 将身份从前端输入改为服务端校验的会话 Cookie。
- 为员工、服务台和管理员建立角色授权。
- 让用户只能访问属于自己的会话、工单、通知、收藏、最近访问与反馈。

## 登录链路

```text
注册 / 登录
  -> 服务端校验密码
  -> 创建 AuthSession 记录
  -> 签发 JWT 并写入 HttpOnly Cookie
  -> 后续请求解析 Cookie
  -> 查询会话记录、用户状态与角色
  -> 注入当前 Principal
```

Cookie 设为 `HttpOnly`，前端 JavaScript 不能直接读取令牌；服务端还保存会话记录，因此登出和改密时可以撤销会话，而不是只能等待 JWT 自然过期。

## 角色设计

| 角色 | 数据范围与能力 |
| --- | --- |
| `employee` | 个人工单、会话、通知和个人工作项；可使用共享知识库 |
| `service_desk` | 在员工能力上增加服务台处理队列 |
| `admin` | 在服务台能力上增加用户角色分配 |

第一个注册用户自动成为管理员，是方便本地演示的引导策略。生产系统通常会改为邀请制、企业 SSO 或预置管理员，而不应让“第一个注册者”自动获得最高权限。

## 关键文件

| 文件 | 阅读重点 |
| --- | --- |
| `knowledgeops/security.py` | 密码哈希、JWT 创建与会话 Cookie 名称 |
| `knowledgeops/api/routers/auth.py` | 注册、登录、登出、个人中心和管理员接口 |
| `knowledgeops/api/dependencies.py` | 当前用户解析与 `require_admin` 等权限依赖 |
| `knowledgeops/models/user.py` | 用户、角色与会话记录 |
| `knowledgeops/frontend/core.js` | 初始化当前用户、登录弹窗、登出与侧边栏角色控制 |
| `knowledgeops/frontend/profile.js` | 个人中心和修改密码 |
| `tests/test_auth_api.py`、`test_session.py` | 会话、角色和隔离测试 |

## 最小复现

1. 在新环境注册账号 A，确认它自动成为管理员。
2. 注册账号 B，确认默认角色为员工。
3. 用 A 打开“用户与权限”，将 B 改为服务台角色；用 B 刷新或重新登录后检查“待我处理”菜单出现。
4. 用 A、B 分别创建工单和对话，互相登录验证对方的个人记录不可见。
5. 点击头像进入个人中心，修改显示名与密码；登出后确认页面回到登录弹窗。

## 部署配置

- `AUTH_JWT_SECRET` 必须替换为独立、随机且长度足够的密钥。
- 生产 HTTPS 环境应设 `AUTH_COOKIE_SECURE=true`。
- `AUTH_ACCESS_TOKEN_TTL_SECONDS` 控制会话时长；改密会撤销该用户的其他有效会话。
- `AUTH_TEST_MODE` 只允许测试显式开启，不能用于部署环境。

## 面试表达

“我没有把当前操作人留在前端输入框，而是改成 HttpOnly Cookie 加服务端会话记录。路由通过依赖注入获取当前用户和角色，业务服务按 user_id 过滤数据。这样登录、登出、密码修改、会话撤销和角色权限是同一条可信链路。”

## 历史记录

- [认证与授权详细日志](../knowledgeops-learning-log-phase20-authentication.md)
- [个人中心与前端结构日志](../knowledgeops-learning-log-phase21-profile-and-frontend-structure.md)
