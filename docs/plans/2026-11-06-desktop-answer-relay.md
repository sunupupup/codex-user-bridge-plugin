# 桌面异步答案转交

用户确认先忽略前端卡片，验收本地回复实际到达原 Codex 聊天。

采用 Hook 落盘队列 + 独立常驻 worker，不让 Hook 等待网络或用户回答。
worker 镜像问题到 local_chat，轮询答案，再通过桌面自带的
send_message_to_thread 通路转交。只处理 native_bridge_probe 标记的异步问题。

此方式是带原问题关联信息的聊天消息转交，不声称完成原生提问卡片。
同步 request_user_input 不接入。PostToolUse 的 accepted 不代表用户已回答。

实施：持久化队列、原数组索引映射、单 worker 锁、超时、提交结果未知不重发；
增加状态机与真实桌面验证。工具通路是当前桌面版本的实验适配，不是稳定公共 API。
不保存管道地址，不修改 Codex 数据库，不启动第二个 App Server 接管会话。

writing-plans skill 当前缺失，本文件兼作最小实施计划。
