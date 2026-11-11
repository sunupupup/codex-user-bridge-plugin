# 三渠道测试

先执行 `uv sync --frozen`，按渠道说明启动对应服务。不同渠道使用独立端口和数据库；同一机器人只运行一个接收服务。

| 渠道 | 默认端口 | 准备 |
|---|---|---|
| local_chat | 5555 | [打开本地聊天网页](./local-chat.md) |
| telegram | 5556 | [创建 Bot、配置私聊账号](./telegram.md) |
| weixin | 5558 | [扫码绑定、发送“你好”建立上下文](./weixin.md) |

通过 `uv run --frozen bridge config set channel 渠道名` 选择本次渠道。

## Tool 模式

1. 设置 `mode tool`，让 Codex 调用 `bridge_send_question`，保存问题编号并确认返回渠道。
2. 在网页或手机确认收到问题。`queued` 仅代表排队，`sent` 代表平台接受，不代表用户已读。
3. 在网页回答；手机引用原通知回复，或发送 `/reply 完整问题编号 回答`。
4. 让 Codex 调用 `bridge_get_reply`，确认 `answered`、正确的 `reply.source` 和 `is_simulated=false`。
5. 重复查询应返回同一答案；另发无关联的普通文字，不应回答其他问题。

每次新测试使用新的 `request_id`，避免复用此前的答案。

## Hook 模式

按 [后台回传](./desktop-answer-relay.md) 启用 Hook 和 worker，再设置 `mode hook`。

1. 让 Codex 使用 `request_user_input_async` 发起标题含 `native_bridge_probe` 的新问题。
2. 在所选渠道回复，不在原生卡片重复回答。
3. 确认原 Codex 聊天实际收到答案并回应；仅看到队列 `submitted` 不足以证明模型已处理。

原生卡片可能保持显示，这是当前限制。测试只发送普通测试文本，无需调用付费 API。

## 已验证

截至 2026-11-11，本地聊天、Telegram、微信均完成真实回复自动回传。微信同时验证了 `/reply` 和引用回复。自动回归为 56 项 Python、7 项 Node 测试通过。
