# 统一模式配置

用户已确认实现 `bridge config set mode tool|hook`、channel 和 show，并更新文档推送。
共享用户配置位于 CODEX_HOME/user-bridge/config.json（默认 ~/.codex），
BRIDGE_CONFIG 可指定隔离路径。默认 tool/local_chat；配置不存放在插件缓存中。

Tool 模式允许新问题，Hook 模式允许异步问题入队。旧任务按原模式和渠道收尾。
工具列表保持稳定，运行时校验模式；不是动态隐藏工具。Hook 保留测试标记筛选。
显式配置优先于历史 BRIDGE_BASE_URL；没有配置时兼容旧工具入口。
按次读取配置，无需为参数切换重启；首次代码升级需要重载插件。
worker 消费已绑定的任务，不因模式切换丢弃旧任务。

验证：配置持久化与非法输入、模式互斥、旧问题跨渠道查询、Hook 索引、原测试回归。
本仓库为独立插件项目，设计记录在 docs/plans，不修改学习仓库 Spec。
沿用 brainstorming 已确认方案；writing-plans skill 当前未提供，本文件兼作实施计划。
