# 配置与模式切换

在源码目录先执行 `uv sync --frozen`，随后使用 `uv run --frozen bridge`。
激活已安装本包的虚拟环境后，可以直接使用 `bridge`。
这是本项目提供的 CLI，不是 Codex 原生命令或设置面板。

```sh
uv run --frozen bridge config show
uv run --frozen bridge config set mode tool
uv run --frozen bridge config set channel telegram
uv run --frozen bridge config set mode hook
```

默认配置：`mode=tool`、`channel=local_chat`、`base_url=http://127.0.0.1:5555`。
保存到 `$CODEX_HOME/user-bridge/config.json`，CODEX_HOME 未设置时使用 `~/.codex`。
源码和安装副本共享此配置。可用 `BRIDGE_CONFIG` 指定独立配置文件；CLI、Hook、MCP
必须使用同一路径。配置不放在插件缓存，不包含 token。

## 模式规则

| mode | 新 Tool 问题 | 新 Hook 任务 | 旧任务 |
|---|---|---|---|
| tool | 允许发送、查询 | 跳过 | 已入队 Hook 任务继续收尾 |
| hook | 拒绝发送 | 捕获带 native_bridge_probe 标记的原生异步提问 | 已登记 Tool 问题仍可查询 |

工具名称仍可能显示在 Codex 中，模式由服务端检查，不靠模型自觉遵守。
同步 request_user_input 不接入。标记筛选仍保留，并非自动转发全部聊天。
旧 Tool 请求在本配置目录的 tool-routes.sqlite3 中绑定地址；重试和查询不改路由。
该功能上线前发送的 Tool 问题没有路由记录，迁移前请先处理完；不要删除路由库。

配置按每次调用读取，修改 mode/channel 不必重启插件；**第一次升级本功能的代码**
仍需更新安装副本并重载插件。新 CLI 不会自动更新插件缓存、安装 Hook、启动或重启进程。
Hook 和 worker 仍按 [后台任务说明](./desktop-answer-relay.md) 安装与启动。

## 渠道和服务

切换 channel 会同时设置默认 base_url：

| channel | 端口 | 模式 |
|---|---|---|
| local_chat | 5555 | tool / hook |
| telegram | 5556 | tool / hook |
| local_mock | 5555 | tool，仅模拟 |
| feishu | 5557 | tool |
| weixin | 5558 | tool / hook |

自定义端口：`uv run --frozen bridge config set base_url http://127.0.0.1:5560`。
再次切换 channel 会重置端口，请先设渠道、再设自定义地址。
hook 模式不接受其他渠道；切换其他渠道前先设置 mode tool。

配置命令只保存并校验配置，不启动服务，也不验证远端账号。
例如 Telegram 服务仍需运行：

```sh
uv run --frozen --env-file .env python scripts/serve.py --channel telegram --port 5556 --db .local/telegram-relay.sqlite3
```

同一机器人只运行一个接收服务。旧任务依赖的旧服务需保持运行直到收尾。
尚未建立配置文件时，Tool 模式兼容原有 BRIDGE_BASE_URL；创建配置后以文件为准。
旧 `.local/desktop-relay-config.json` 不再读取，请用上述命令显式迁移。

## 验证范围

2026-11-06：Python 全量 50 项、Node worker 6 项通过；CLI show/set 已执行验证。
测试期间本机使用 hook + telegram，MCP 子进程仍通过隔离配置完成回归。

自动测试覆盖配置校验、非法值不覆盖文件、Hook 模式旁路、重复 Hook、
Tool 模式约束及旧问题路由。此前本地和 Telegram 自动转交实测见后台任务说明。
本次配置改造不代表已额外完成一次真实手机收发测试。
