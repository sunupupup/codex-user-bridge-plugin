# 桌面异步答案转交（本地聊天 / Telegram 实验）

## Telegram 路由

可另开 `uv run --frozen --env-file .env python scripts/serve.py --channel telegram --port 5556 --db .local/telegram-relay.sqlite3`，保留 5555 本地页面。
同一机器人只能有一个接收进程，启动前先停止已有的 Telegram 接收服务。
在 `.local/desktop-relay-config.json` 写入：
`{"channel":"telegram","base_url":"http://127.0.0.1:5556"}`。
此后新问题转发 Telegram；已入队问题保留原渠道和地址，不迁移历史问题。
手机需引用机器人问题回复。worker 检查 Telegram 答案来源后转交 Codex。
切回本地使用 `{"channel":"local_chat","base_url":"http://127.0.0.1:5555"}`。
该配置不含 token；凭据仍从未提交的 `.env` 读取。

链路：原生 request_user_input_async → PreToolUse 写队列立即返回 →
独立 worker 镜像问题到 5555 → 用户页面回复 → worker 转交原聊天 → Codex 继续处理。

只处理标题含 `native_bridge_probe` 的异步问题。普通问题与同步
request_user_input 不启用转交。PostToolUse 不是用户回答事件。

## 启动

1. 本地服务：`uv run --frozen python scripts/serve.py --channel local_chat --port 5555 --db .local/local-chat.sqlite3`
2. 已授权的 PreToolUse Hook 指向 `scripts/desktop_hook_probe.py`。
3. **在 Codex 执行环境中**运行 `node scripts/desktop_answer_worker.mjs`。
   普通终端通常没有 CODEX_APP_TOOLS_PIPE_PATH；缺失时明确报错。
   `--check` 可只检查桌面工具可用性。不复制或持久化管道地址。
4. 发起带标记的新异步问题，在 localhost:5555 回答。

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

## 2026-11-06 实测

- 原生调用 call_37729a8acc5947ab9445c6455637f1e9。
- 本地问题 q_2209bdd5bbbe47afa6ade1236c9777bb。
- 用户在本地页面回答“今天天气不错”。
- 后台自动发送到原聊天，当前 Codex 实际收到该文本并回应；没有由模型手动查询答案。
- 原生卡片关闭与双端去重尚未验证/实现。

验证命令：`node --test tests/desktop_answer_worker.test.mjs`；
`uv run --frozen python -m unittest discover -s tests -v`。

## 2026-11-06 Telegram 实测

- 使用独立的 5556 Telegram 服务，5555 本地页面继续运行。
- Hook 将新问题的渠道和地址固化入队，后台按绑定渠道处理；旧问题不迁移。
- 问题编号：`q_1e4b7a7670a24e1b862ef932e51dbd8f`。
- 发送结果：`channel=telegram`、`delivery_status=sent`、`is_simulated=false`。
- 用户在手机回复并要求写一个小朋友上学的短故事；后台自动转交原 Codex 聊天，
  Codex 实际收到并写出故事。没有由模型手动调用查询工具来获取答案。
- 队列最终状态 `submitted`，桌面返回 `success=true`；结合实际模型回应确认闭环完成。
- 本轮针对性验证：Node 状态机测试 6 项、Python Hook 队列测试 1 项通过。
  覆盖 Telegram 渠道/答案来源校验、失败与重复发送、原问题索引和重复 Hook。
- 尚未完成：原生卡片状态同步、双端回答去重、桌面端回答后取消后台等待。

测试账号凭据、私聊 ID、运行队列和数据库均留在本机，不纳入仓库。
