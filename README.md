# Codex User Bridge Plugin

离开电脑后，也能回答 Codex 的问题。

通过**本地聊天网页、Telegram 或微信**接收提问并回复，支持 MCP 工具主动收发，以及 Hook 后台自动转交两种模式。三个渠道均已完成真实回复回传测试。

## 选择交互模式

| | Tool 模式 | Hook 模式 |
|---|---|---|
| 发起问题 | `bridge_send_question` | 捕获带标记的 `request_user_input_async` |
| 接收答案 | Codex 调用 `bridge_get_reply` | 后台 worker 自动转交原 Codex 聊天 |
| 适合场景 | 按需通知，在合适时机查询 | 离开电脑后，从手机回答并继续任务 |
| 运行条件 | 插件 + 渠道服务 | 额外配置 PreToolUse Hook、启动 worker |

发送和单次查询不会等待用户回答。Codex 可以继续处理不依赖答案的工作，需要用户决定的操作仍应等待回复。

Hook 模式目前只捕获带 `native_bridge_probe` 标记的异步问题。答案作为关联原问题的新消息转交，**不会关闭原生 Question 卡片**；不支持替代同步审批。桌面通信适配仍属实验功能。

## 三个渠道

| 渠道 | 回复方式 | 使用说明 |
|---|---|---|
| 本地聊天 | 浏览器输入答案，适合调试与演示 | [本地聊天](./docs/local-chat.md) |
| Telegram | 引用机器人通知回复，或使用 `/reply` | [Telegram 配置](./docs/telegram.md) |
| 微信 | 引用 ClawBot 通知回复，或使用 `/reply` | [微信配置](./docs/weixin.md) |

截至 2026-11-11，三个渠道均已验证“发送问题 → 用户回答 → 自动转交原 Codex 聊天”。长期无人值守的稳定性仍需持续验证。

## 快速开始

需要 Python 3.11+、[uv](https://docs.astral.sh/uv/getting-started/installation/) 和 Codex CLI；Hook 模式另需 Node.js 与 Codex 桌面环境。

```powershell
git clone https://github.com/sunupupup/codex-user-bridge-plugin.git
cd codex-user-bridge-plugin
uv sync --frozen
uv run --frozen bridge config set mode tool
uv run --frozen bridge config set channel local_chat
uv run --frozen python scripts/serve.py --channel local_chat --port 5555 --db .local/local-chat.sqlite3
```

保持服务运行，在浏览器打开 http://127.0.0.1:5555 。另开终端，在仓库根目录安装插件：

```powershell
codex plugin marketplace add .
codex plugin add codex-user-bridge@codex-user-bridge
```

重新打开 Codex 聊天，必要时重启 App，然后输入：

> 使用 external-user-chat 技能发送一个本地测试问题。发送后先介绍通信流程，再查询回答；如果还没有回复，保留问题编号。我会在本地网页回答。

也可直接从 GitHub 安装插件目录；渠道服务仍需单独启动：

```powershell
codex plugin marketplace add sunupupup/codex-user-bridge-plugin
codex plugin add codex-user-bridge@codex-user-bridge
```

## 配置与后台回传

```powershell
uv run --frozen bridge config show
uv run --frozen bridge config set channel telegram
uv run --frozen bridge config set mode hook
```

默认是 `tool + local_chat`。配置按调用读取，新问题使用新设置，旧问题保留原路由。配置命令不会启动服务、安装 Hook 或重载插件代码。

- [配置与模式切换](./docs/configuration.md)：渠道、端口、配置路径。
- [Hook 后台回传](./docs/desktop-answer-relay.md)：运行条件、启动和限制。
- [三渠道测试](./docs/channel-testing.md)：验证通知、回复和自动转交。

## 工作原理

```text
Tool：Codex → MCP 发送工具 → 渠道服务 → 用户
      用户回复 → SQLite → MCP 查询工具 → Codex

Hook：原生异步提问 → PreToolUse 入队 → worker → 渠道服务 → 用户
      用户回复 → SQLite → worker → 原 Codex 聊天
```

同一 `task_id + request_id` 重试不会重复创建问题；查询使用返回的 `question_id`。手机回复通过引用消息或问题编号关联，普通聊天不会被猜测为某道题的答案。

发送结果未知时不自动重发；重复渠道回复保留首条有效答案。原生卡片与外部渠道同时回答的协调尚未实现。

服务仅监听本机。账号凭据、数据库与队列留在本地，不应提交或公开；同一机器人只运行一个接收服务。

## 开发与限制

```powershell
uv run --frozen python -m unittest discover -s tests -v
node --test tests/desktop_answer_worker.test.mjs
uv run --frozen python scripts/verify_plugin.py
```

2026-11-11：56 项 Python 测试、7 项 Node 测试通过。测试覆盖路由、幂等、消息关联、持久化和异常处理；真实渠道回传另经人工与桌面操作验证。

核心目录：`.codex-plugin/` 插件清单、`.mcp.json` 工具服务配置、`skills/` 使用指引、`src/` 渠道与存储、`scripts/` 配置及后台任务、`tests/` 自动测试。

后续主要工作：简化 Hook 与 worker 安装和进程管理、协调双端回答、同步原生卡片状态。当前版本适合个人使用和演示，桌面升级后应重新验证 Hook 回传。

[更新记录](./CHANGELOG.md) · [MIT 许可证](./LICENSE)
