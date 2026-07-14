# 批C 矩阵零头清账证据(2026-07-14,owner 拍板④「白天顺手清」)

判读+完整叙事见 `../01_batch_c_execution_plan_draft.md` §7「矩阵零头清账」节。本目录=从易失 scratchpad(`.artifacts/`,/tmp 重启即清)归档的关键 JSON + ledger 段。

## 头号发现:prod 数据形态 gap(flip 前必修)
门6 prod 注入式演习一发即死在共享 snapshot 构建:`build_validated_state_snapshot`(state_snapshot.py:1730)**无条件先建 F1 投影**、在任何 family 生成前;F1/F6 投影用 `master_scalar_coercions=False`(strict snapshot scalars)要求 pose_params exact str,而 prod frozen `candidate_placements.json` 的 `boundary_storage_port.orientation` 是 int(该设施 placement_rule=`left_or_bottom_boundary` 落在 F1/F6 规则集内)。→ **prod 真数据上整条 cut attach fail-closed 中止,不止 F1/F6,连 power(F7)都到不了生成**。fail-closed 方向、零 soundness 风险,但 flip 后框架 prod 上完全不可用。新增 promotion 前置「prod 形态适配批」(sealed 双文件,roadmap 台账#8 待 owner 过目)。

## 文件
- `gate6_drill_arm1_cell.json` — 门6 全族注入演习(6×6 cap=200):LBBD UNKNOWN@566s,drill 两轮均命中上述 gap(SnapshotValidationError),coordinate_framework_cut_count=0。兼作 D-1 restart 链**段A**(fresh_start,seal tail_hash `4bb6fe79…`)。
- `pic5_multi_rect_sequence.json` — PIC-5 多 rect 序列(6×6→6×7→7×6,同 session):全绿,LBBD wall 565/552/542s 跨尺寸稳定;ledger 血缘连续段逐环正确;gap 三 rect 确定性同错=非偶发。
- `d1_restart_segB_cell.json` — D-1 oracle 重生成开销**段B**(跨运行重启,`recovery_reason=restart_drill`,predecessor 指向段A):session 31.7s+master build 15.6s+master 重解 563.7s+bundle 重建 28.0s=restart 全量重生成开销(RFC-003 非消费:ledger 永不作 cut 来源)。段B seal tail_hash `fab091ad…`。
- `ledger_segments/` — 上述各 run 的 ledger 段(GENESIS 血缘可核):`segA_arm1_drill`(fresh)/`pic5_rect1-3`(同进程序列链)/`segB_restart_drill`(跨运行重启链,predecessor=段A tail `4bb6fe79…`)。

## 门7 rollback 演练(臂2)改判
gap 下全族都到不了 attach 环,关族对照判定力归零→改「适配批修复后随门6『触发>0』复跑」,不烧 25min prod solve。

## probe_15r(过夜穷尽臂)
非阻塞观测项(自然触发降观测项,拍板③),暂缓;主线按「未跑过」推进。

## 复现
`../injection_drill_runner.py`(门6 演习 harness)、`../multi_rect_sequence_runner.py`(PIC-5 外循环)。用法见各文件 docstring。均为 sanctioned 直建形态(clean-room 构建→构建后 export attach env→run_with_status;真编排入口在 sealed 守卫层、certified 下 attach fail-closed)。
