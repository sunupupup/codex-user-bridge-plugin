# 个人微信（ClawBot / iLink）

此渠道连接腾讯公开的 ClawBot/iLink 机器人，不是企业微信 Webhook，也不会控制普通微信好友或群聊。不需要安装 OpenClaw。你的微信账号是否能扫码绑定，以手机端实际结果为准。

## 1. 扫码登录

在仓库根目录运行（Python 3.11+、uv）：

```powershell
uv sync --frozen
uv run --frozen python scripts/weixin_setup.py
```

手机微信扫描终端二维码，按手机提示确认；需要配对验证码时在终端输入。过期可重新运行。登录后凭据仅保存在 `.local/weixin-account.json`，目录已被 Git 忽略。不要分享二维码、凭据或该目录。自定义路径可用 `WEIXIN_CREDENTIALS`，登录助手和服务必须使用同一路径。

## 2. 启动微信服务

使用独立的 5558 端口，可保留本地聊天和 Telegram 服务：

```powershell
uv run --frozen --env-file .env python scripts/serve.py --channel weixin --port 5558 --db .local/weixin.sqlite3
```

没有 `.env` 时可去掉 `--env-file .env`；微信默认直接读扫码凭据文件。服务启动后，在手机给该机器人发一条“你好”，建立会话上下文。普通聊天不会自动成为某个问题的答案。

## 3. 从 Codex 测试

先执行 `uv run --frozen bridge config set channel weixin`。在新聊天中说：“通过 user bridge 问我是否继续这次测试，稍后查询回答。”应返回 `channel: weixin`。推荐在微信引用原通知，直接输入答案；也可使用通知里的完整编号：

```text
/reply q_通知里的32位问题编号 继续
```

请使用通知中的完整真实编号。让 Codex 查询同一问题，应得到 `answered`、`reply.source: weixin`、`is_simulated: false`。引用回复已完成真实桌面微信测试。语音或图片暂不支持。

## 状态与限制

- `queued` 且提示等待上下文：先给机器人发消息，随后自动尝试发送。
- 微信 `-2`：原因可能涉及上下文或平台策略；清除旧上下文并等待新的手机入站消息后再尝试，不用旧 token 循环重试。
- `-14` 登录失效：停止服务、重新扫码、再启动；新问题保留队列，已经 failed 的问题不会自动重发。
- `unknown`：平台可能已接收，但本地没收到确认；不会自动重发。不要立刻换编号重复通知。
- 接收采用最长约 35 秒的平台长轮询，通知可能需要等待本轮返回；退出也可能等待在途请求结束。
- 同一账号只运行一个接收进程，不要与另一个 OpenClaw 实例争抢消息。换账号请使用新的数据库。

协议依据为腾讯维护的 [openclaw-weixin 协议与源码](https://github.com/Tencent/openclaw-weixin/blob/main/docs/protocol_zh_CN.md)。该文档也说明客户端字段不等于完整服务端契约。会话上下文有效期没有在本插件中写死；[上游用户反馈](https://github.com/Tencent/openclaw-weixin/issues/309)显示长期无人发言后的通知可能被拒绝，具体窗口仍需你的账号实测。协议兼容版本与本项目版本分开：按上游文档声明 3.0.1 协议，bot_agent 保留 CodexUserBridge 身份。

本地已覆盖模拟平台 HTTP、消息去重、身份绑定、会话失效、登录文件与真实 MCP 子进程。2026-11-11 已使用真实微信账号验证通知、/reply 回复、引用回复及 Codex 自动接收；长期无人值守可靠性仍未验证。

## Hook 自动回传

选择 weixin 渠道后，按 [后台回传](./desktop-answer-relay.md) 启用 Hook 模式和 worker。收到答案后自动转交原聊天，原生卡片暂不自动关闭。

登录二维码可保存为图片：
`uv run --frozen python scripts/weixin_setup.py --qr-file .local/weixin-login.png`。
图片只保存在本机的忽略目录；过期后重新生成。

2026-11-11：真实微信闭环通过；桌面微信引用通知发送测试文本后，数据库保存答案、worker 状态为 submitted，原 Codex 聊天实际收到转交消息。真实引用字段为 ref_msg.message_item.msg_id，已加入回归测试。

引用回复只用引用字段定位原题，答案取新输入正文；普通“可以”不自动归到最近问题。已回答的问题保持首条有效答案，不会因引用旧题再次触发执行。
