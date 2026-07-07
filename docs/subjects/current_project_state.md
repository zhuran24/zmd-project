# 当前项目状态

更新时间：2026-07-07。

P1.2 已于 2026-07-07 由 owner 显式 `owner_manual_decision` 正式 CLOSED，owner 手动 phase gate 为 `closed_manual_owner_decision`，`p1_3b_entry_allowed=true`、`next_phase_entry.allowed=true`。这只表示 P1.3 准许开工，不表示 P1.3 主体已完成。V99 close-kernel、fixed-witness、P1.2 open gate、whole-layout independent reverify 和 PR1 producer/supervisor mint split 已在当前工作树落地。未提交工作树还收拢了 viewer、report、IndustrialPlanner 和 generic writer 的外围发布面。

当前 authority API 链是：producer 提交 `CANDIDATE_PROPOSED`，`ExactCampaign.supervisor_seal()` 可铸造磁盘持久化终端 `CERTIFIED`，`publish_verified_certified_delivery_surface()` 可事务式发布 canonical artifacts。production supervisor 入口是独立命令 `scripts/run_supervisor_seal.py`（`349c56c`，2026-07-04）；普通 solver run 仍只到 proposal，且尚无真实生产 campaign→seal 实跑记录，不能称为端到端发布链已打通。

发布时点待办包括 PR2 的最小可信 L0/L1 supervisor、受控 loader/read-once/import closure、review package 的默认测试覆盖与 treeish/archive policy 问题，以及 #9a 部署时点生产 byte re-pinning。面向人的当前阶段统一称 P1.3；JSON 和旧测试中的 `p1_3b_*` 仅保留为兼容机器标识。P1.3 主体仍是 `step_8_apply_to_master` 生产 master/cut 集成。
