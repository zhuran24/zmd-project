# 当前项目状态

更新时间：2026-06-26。

P1.2 仍未闭合，owner 手动 phase gate 为 `blocked_manual_review_count`，`p1_3b_entry_allowed=false`。V99 close-kernel、fixed-witness、P1.2 open gate、whole-layout independent reverify 和 PR1 producer/supervisor mint split 已在当前工作树落地。未提交工作树还收拢了 viewer、report、IndustrialPlanner 和 generic writer 的外围发布面。

当前 authority API 链是：producer 提交 `CANDIDATE_PROPOSED`，`ExactCampaign.supervisor_seal()` 可铸造磁盘持久化终端 `CERTIFIED`，`publish_verified_certified_delivery_surface()` 可事务式发布 canonical artifacts。当前没有 production supervisor CLI/launcher，所以普通 solver run 只到 proposal，不能称为端到端发布链已打通。

仍未闭的是 PR2 的最小可信 L0/L1 supervisor、受控 loader/read-once/import closure，review package 的默认测试覆盖与 treeish/archive policy 问题，以及 owner 手动 close gate。面向人的下一阶段统一称 P1.3；JSON 和旧测试中的 `p1_3b_*` 仅保留为兼容机器标识。
