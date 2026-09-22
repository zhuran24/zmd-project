# 历史内核复核探针源码

日期：2026-09-20。性质：历史测试源码，未纳入当前工作区自动验收。这里保存从复核证据树迁出的4个小型Cargo探针项目；原路径与字节指纹见[迁移清单](../../evidence/revision-r3/cleanup.json)。

kernel依赖指向当前源码。`r2_records`曾依赖已删除的历史仓库快照，因此以现有内核重新编译的结果不能冒称旧实现复现。需要编译时须显式设置`CARGO_TARGET_DIR=/home/zhuran24/zmd-research-fresh/求解器/target`；不得在这些目录建立独立target。

当前自动回归入口为工作区`cargo test --locked --offline`，第4轮证据见[修订与验证](../../evidence/revision-r4/修订与验证.md)。
