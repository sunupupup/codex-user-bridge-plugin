# 本地聊天

无需外部账号，在浏览器中接收 Codex 提问并回答，适合开发、测试和演示。

在仓库根目录执行：

```powershell
uv sync --frozen
uv run --frozen bridge config set channel local_chat
uv run --frozen python scripts/serve.py --channel local_chat --port 5555 --db .local/local-chat.sqlite3
```

打开 http://127.0.0.1:5555 。页面每两秒更新，显示最近 200 个问题；输入答案或选择候选项后发送。问答保存在 SQLite，刷新页面不会丢失。

Tool 模式由 Codex 调用 `bridge_get_reply` 查询；Hook 模式由已启动的 worker 自动转交，配置见 [后台回传](./desktop-answer-relay.md)。

服务只监听本机，Ctrl+C 停止。`source=local_chat`、`is_simulated=false` 表示浏览器手动回答，不代表远端身份认证。
