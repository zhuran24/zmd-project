# 运行与维护入口

本页只负责把操作任务路由到对应的 current guide。它不复制 gate、hash、测试数量、开关值或 release 状态；这些值回到 [CURRENT](CURRENT.md)、机器源与具体命令输出。

## Agent 与文档操作

- 耐久 agent 操作协议：[`AGENT_OPERATIONS.md`](AGENT_OPERATIONS.md)；根 `CLAUDE.md` / `AGENTS.md` 仅为可选 workspace overlay
- 详细 agent 操作、测试、冻结与故障处理：[AGENT_OPERATIONS](AGENT_OPERATIONS.md)
- 修改任一路径前：`.venv/bin/python devtools/docctl.py context <path> --intent edit`
- 完成文档变更后：`.venv/bin/python devtools/docctl.py check --changed`
- 文档分区与局部前门：[SECTION_INDEX](SECTION_INDEX.md)
- 文档系统常态维护与框架再开启边界：[STEADY_STATE](governance/document-system/STEADY_STATE.md)

## 求解、campaign 与并行

- exact campaign 主操作面：[exact_campaign_operations.md](exact_campaign_operations.md)
- frontier probe 策略：[frontier_probe_strategy.md](frontier_probe_strategy.md)
- 并行配置：[parallel_configuration.md](parallel_configuration.md)
- 环境变量索引：[env_variable_index.md](env_variable_index.md)
- 脚本入口与用途：[scripts/README.md](../scripts/README.md)
- Pumpkin PoC 局部说明：[scripts/pumpkin_poc/README.md](../scripts/pumpkin_poc/README.md)

## 测试、review 与发布边界

- 工作流测试：[项目说明/15_workflow_testing.md](项目说明/15_workflow_testing.md)
- review 纪律：[项目说明/16_workflow_review.md](项目说明/16_workflow_review.md)
- telemetry：[项目说明/17_workflow_telemetry.md](项目说明/17_workflow_telemetry.md)
- 环境配置：[项目说明/18_workflow_env_config.md](项目说明/18_workflow_env_config.md)
- 坑册与 SOP：[项目说明/28_pitfalls_and_sop.md](项目说明/28_pitfalls_and_sop.md)
- certified 与 owner 边界：[PROJECT_LOCK](../PROJECT_LOCK.md)

checker、solver PASS、seal 或本地 artifact 只证明各自声明的层；它们不会自动授予 owner close、数学 soundness 或 durable `CERTIFIED`。

## 历史 adapter delivery

2026 年 4 月的 IndustrialPlanner single-base delivery 文档已冻结为历史证据。入口见 [history/deliveries](history/deliveries/README.md)；当前兼容边界见 [compatibility_matrix](compatibility_matrix.md)。
