# Hook 后台答案回传

支持本地聊天、Telegram 与微信。PreToolUse 将原生异步问题入队后立即返回，常驻 worker 发送通知、等待答案，再通过 `send_message_to_thread` 转交原 Codex 聊天。

只处理标题含 `native_bridge_probe` 的 `request_user_input_async`；同步提问和普通问题不进入此链路。PostToolUse 不是用户回答事件。

## 启动

1. 按 [本地聊天](./local-chat.md)、[Telegram](./telegram.md) 或 [微信](./weixin.md) 启动服务，并用 `bridge config set channel` 选择对应渠道。
2. 已授权的 PreToolUse Hook 指向 `scripts/desktop_hook_probe.py`。
   执行 `uv run --frozen bridge config set mode hook` 启用入队；默认 tool 模式跳过 Hook。
3. **在 Codex 执行环境中**运行 `node scripts/desktop_answer_worker.mjs`。
   普通终端通常没有 CODEX_APP_TOOLS_PIPE_PATH；缺失时明确报错。
   `--check` 可只检查桌面工具可用性。不复制或持久化管道地址。
4. 发起带标记的新异步问题，在所选渠道回答。

worker 是独立常驻进程，不由 Hook 反复创建。Ctrl+C 停止；它依赖当前
Codex 桌面环境，不保证退出桌面后继续工作。现有运行管理器结束它后需重新启动。

## 状态与限制

`.local/desktop-answer-queue/*.json` 保存关联信息和状态：
queued → waiting → sending → submitted。submitted 仅表示桌面转交 API 接受；
还需看到目标聊天回应，才能证明模型收到。提交超时、断线或 sending 状态重启
标记 unknown，不自动重发。任务一小时过期；拒绝模拟答案。

锁文件避免多个 worker 同时消费；异常退出留下 worker.lock 时，先核对文件内 PID
对应的进程已经退出，再删除该锁重启。不要删除活跃进程的锁。

当前走桌面自带 send_message_to_thread 的消息转交通路，模型收到 codex_delegation
消息，**不伪装成原生表单提交，不保证关闭卡片**。未实现用户在 Codex 卡片回答后
自动取消本地任务，双端回答可能产生重复语义。这不是同步审批的替代实现。
桌面管道协议来自当前安装版本，属于实验适配，升级后应重新验证。

配置路径与模式切换见 [配置说明](./configuration.md)，验证步骤见 [三渠道测试](./channel-testing.md)。
