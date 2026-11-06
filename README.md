# Codex User Bridge Plugin

让 Codex 在需要用户输入时，通过本地聊天或手机通知用户，并接收回答。提供两种方式：**两个 MCP Tool 主动收发**，或 **原生异步提问 + Hook + 后台任务自动转交**。

**本地聊天与 Telegram 已测试跑通，包括用户回复自动送回当前 Codex 聊天并继续执行。** 飞书应用机器人和个人微信 ClawBot/iLink 已有工具渠道实现及模拟测试，真实设备联调尚待验证。

## 两种使用方式

通过命令行切换（先执行 `uv sync --frozen`）：

```sh
uv run --frozen bridge config show
uv run --frozen bridge config set mode tool
uv run --frozen bridge config set channel telegram
uv run --frozen bridge config set mode hook
```

默认 `tool + local_chat`。设置 `hook` 后，新 Tool 发送被拒绝；设置 `tool` 后，
Hook 不再为新问题入队。旧问题仍按原路径收尾。切换参数无需重启，首次代码升级需重载插件。
配置不会自动启动渠道服务或 worker。完整说明见 [配置与模式切换](./docs/configuration.md)。

| | 方式一：两个 Tool | 方式二：Hook + 后台任务 |
|---|---|---|
| 发起问题 | Codex 调用 `bridge_send_question` | Codex 调用原生 `request_user_input_async`，`PreToolUse` 捕获问题 |
| 接收答案 | Codex 主动调用 `bridge_get_reply` 查询 | 常驻 worker 轮询，通过 `send_message_to_thread` 自动转交原聊天 |
| 是否等待用户 | 发送和单次查询立即返回 | Hook 仅入队即返回，后台负责等待 |
| 答案形式 | 查询工具的结果 | 携带原问题关联信息的追加消息 |
| 启用方式 | 安装插件并启动渠道服务 | 额外配置 Hook、启动 worker；当前是实验模式 |

同一个问题选择一条路径即可。两条路径都允许 Codex 继续处理不依赖答案的工作；必须依赖用户决定的操作仍需等待答案。

### 方式一：两个 Tool

`bridge_send_question` 返回问题编号；稍后用相同 `task_id` 和该 `question_id` 调用
`bridge_get_reply`。这条路径不会自动向聊天插入消息，也不保证模型定时查询。
下方快速开始和插件安装步骤适用于此方式。

### 方式二：原生异步提问 + Hook + 后台任务

```text
request_user_input_async → PreToolUse 将问题写入队列 → Hook 立即返回
常驻 worker → 本地聊天 / Telegram → 用户回答
常驻 worker → send_message_to_thread → 原 Codex 聊天收到答案并继续处理
```

**Hook 创建任务，提前启动的 worker 执行任务**，不是每次提问都新建一个进程。
原生异步工具自行返回 `accepted`，插件不修改其 tool result。
当前只处理带 `native_bridge_probe` 标记的问题，安装插件不会自动开启这条链路。
原生 Question 卡片状态暂不同步；追加消息不等于原生表单提交。

配置、启动和实测证据见 [后台答案转交说明](./docs/desktop-answer-relay.md)。

## 渠道验证状态

截至 2026-11-06：

| 渠道 | 两个 Tool 收发 | Hook + 后台自动转交 |
|---|---|---|
| 本地聊天 `local_chat` | 已实测真人页面回复 | 已实测自动送回原聊天，并继续发起新问题 |
| Telegram | 已实测机器人通知与手机回复 | 已实测手机回复自动送回，Codex 按回复写出故事 |
| 飞书 / 个人微信 | 模拟 API 与 MCP 测试通过，真实设备待验证 | 尚未接入 |
| `local_mock` | 自动模拟测试通过，不能当作真人回答 | 不接入，worker 拒绝模拟答案 |

Telegram 的 Bot 创建、.env 配置、私聊 ID 查询和启动步骤见 [Telegram 使用说明](./docs/telegram.md)。

飞书的应用、open_id 与长连接配置见 [飞书使用说明](./docs/feishu.md)。

个人微信的扫码登录和会话限制见 [微信使用说明](./docs/weixin.md)。三个渠道逐个测试见 [测试入口](./docs/channel-testing.md)。

## 项目结构

```text
codex-user-bridge/
├── .codex-plugin/plugin.json       # Codex 兼容插件清单
├── .mcp.json                       # MCP 启动配置，无开发机绝对路径
├── .agents/plugins/marketplace.json # 本地插件目录
├── skills/external-user-chat/      # 工具使用时机
├── src/codex_user_bridge/          # MCP 工具、Adapter、HTTP 服务与存储
├── scripts/                       # 安装准备、启动、演示与安装验证
├── tests/                         # 自动检查
├── docs/                          # 设计与验收记录
├── pyproject.toml                 # Python 包及命令入口
├── uv.lock                        # 锁定依赖
├── CHANGELOG.md
└── LICENSE
```

这是官方仍支持的 `.codex-plugin` 兼容布局。使用此布局是因为已在 Codex CLI 0.163.0-alpha.10.2 验证插件加载；没有宣称通过官方插件商店审核。

## 快速开始

需要 Python 3.11+、[uv](https://docs.astral.sh/uv/getting-started/installation/)，安装到 Codex 时还需要 Codex CLI。

在本项目根目录执行：

```powershell
uv sync --frozen
python scripts/serve.py
```

默认启动 `local_chat` 手动聊天模式。浏览器打开 `http://127.0.0.1:5555`，Codex 发来的问题会自动出现；输入回答或点候选答案后点击发送，再让 Codex 查询。页面每两秒更新，刷新不会丢失已保存的问答。最近显示 200 个问题。

只监听本机，数据库保存在项目 `.local/messages.sqlite3`。`source: local_chat`、`is_simulated: false` 表示本机浏览器的手动回答，不代表验证了远端用户身份。Ctrl+C 停止；Windows 可双击 `start.cmd`。

需要原来的自动模拟时，改用 `python scripts/serve.py --channel local_mock`。它每 3 秒扫描并生成模拟回答，不能视为真人授权。

在自动模拟模式下，第二个终端运行：

```powershell
uv run --frozen python scripts/demo.py
```

预期输出：发送 `pending` → 主动查询 → `answered`，回复带 `source: local_mock`、`is_simulated: true`。演示程序的定时查询不等于模型会自动定时运行。

## 安装到 Codex

从 GitHub 添加本仓库作为插件目录：

```powershell
codex plugin marketplace add sunupupup/codex-user-bridge-plugin
codex plugin add codex-user-bridge@codex-user-bridge
```

也可先克隆本仓库，在本地运行 5555 服务：

```powershell
git clone https://github.com/sunupupup/codex-user-bridge-plugin.git
cd codex-user-bridge-plugin
uv sync --frozen
python scripts/serve.py
```


保持 5555 服务运行，在本项目根目录执行：

```powershell
codex plugin marketplace add .
codex plugin add codex-user-bridge@codex-user-bridge
```

重新打开 Codex 聊天，必要时重启 App。MCP 配置中的相对 `cwd` 由 Codex 解析为插件安装目录；`uv run` 在该副本准备依赖并启动工具，不引用原开发目录。

测试提示：

> 使用 codex-user-bridge 的 external-user-chat 技能发送一个本地测试问题。发送后先解释通信流程，再查询回答；只展示模拟结果，不执行真实付费操作。仍待回复时保留问题编号。

查看或卸载：

```powershell
codex plugin list --marketplace codex-user-bridge --json
codex plugin remove codex-user-bridge@codex-user-bridge
```

安装和日常工具调用本身不需要模型 Key；运行真实 Codex 模型任务使用你的账号额度。首次从缓存副本启动可能需要下载 Python 依赖，需能访问 Python 包源。

## 两个 Tool 的调用链与约定

```text
Codex → bridge_send_question → LocalHttpAdapter.send → POST /chat
                                                   → SQLite 保存 pending

用户在本地页面或外部渠道回复 → 服务保存 answered
（仅 local_mock 模式由定时线程生成模拟回答）

Codex → bridge_get_reply → LocalHttpAdapter.get_reply → GET /chat/{id}?task_id=...
                                                     → 工具结果返回回答
```

| 模块 | 职责 |
|---|---|
| [Skill](./skills/external-user-chat/SKILL.md) | 何时发问、何时查询；不提供后台定时调度 |
| [mcp_server.py](./src/codex_user_bridge/mcp_server.py) | 两个 MCP 工具的参数、说明和结构化结果 |
| [adapters.py](./src/codex_user_bridge/adapters.py) | 统一 send/get_reply，隔离渠道协议 |
| [service.py](./src/codex_user_bridge/service.py) | HTTP 接口、页面服务与渠道线程启动 |
| [store.py](./src/codex_user_bridge/store.py) | 问题保存、幂等与状态推进 |

发送参数：

```json
{"task_id":"demo-001","request_id":"question-001","message":"本地测试收到吗？","options":["收到","稍后"]}
```

查询使用相同 `task_id` 和返回的 `question_id`。task_id 由调用者选定，不是自动读取的 Codex 会话 ID。

- 同一 task_id + request_id 重试不会重复创建问题；同键改内容返回 409。
- 查询不消费回答；任务标识不匹配或问题不存在返回 404。此机制防止串答，不是身份认证。
- 服务不可用时明确报告结果未知；重试沿用原 request_id。
- 回答是工具结果，不自动插入 user message，也不自动唤醒 Goal。
- 模拟回复永远不能授权真实花费或其他需用户决定的操作。
- Telegram 返回 queued 只代表排队，sent 只代表平台接受；unknown 不会自动重发。真人回答也仅适用于原问题。
- 仅供本机单用户实验，无账号认证；不要对局域网或公网开放，不发送密钥。

## 已完成与待办

- [x] 两个 MCP Tool：发送问题、主动查询答案。
- [x] Hook 入队、后台轮询，并自动转交原 Codex 聊天。
- [x] 本地聊天与 Telegram 真实回复闭环验证。
- [ ] 原生 Question 卡片标记为已回答，与外部答案同步。
- [ ] 双端重复回答处理、Codex 端回答后取消后台等待。
- [ ] 简化 Hook、worker 的安装配置和进程管理。

目前自动转交使用桌面通信管道的实验适配，升级后需要重新验证。
同步 `request_user_input` 不属于此 Hook 自动转交能力。
历史同步协议实验与原生卡片待办见 [原生提问实验](./docs/native-input-probe.md)。

## 验证与开发

```powershell
uv run --frozen python -m unittest discover -s tests -v
node --test tests/desktop_answer_worker.test.mjs
python scripts/verify_plugin.py
# 需要先启动 5555 服务；从独立安装缓存验证收发
python scripts/verify_plugin.py --roundtrip
```

Python 检查涵盖渠道模拟 API、MCP 端到端、Hook 队列与统一配置；另有 Node worker 测试 6 项。worker 需要 Node.js。最新配置改造的测试记录见 [配置说明](./docs/configuration.md)。
本地聊天与 Telegram 的真实自动回传记录见 [后台答案转交说明](./docs/desktop-answer-relay.md)；
早期 CLI 模拟渠道及安装检查见 [验收记录](./docs/validation.md)。安装验证使用独立临时配置，不改日常 Codex 配置、不调用模型。

[设计](./docs/plans/2026-10-20-local-bridge-design.md) · [更新记录](./CHANGELOG.md) · [MIT 许可证](./LICENSE)

术语：MCP 是宿主调用工具的协议；stdio 是子进程标准输入输出通信；Adapter 是渠道适配器；Polling 是主动查询；幂等表示重试同一个请求不重复创建问题。

[官方插件打包说明](https://developers.openai.com/plugins/build/plugins) · [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
