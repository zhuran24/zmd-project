# 批 1E 前置件：剪杆义务条目文字草案（PO-CERTIFIED-POWER-POLE-DOMINANCE-NORMALIZATION）

> 2026-07-10 主会话起草（1D 实现进行中；本稿基于 1C 已收口事实——测试名/代码落点已稳定，
> evidence 行号与 source pins 留 1E 实施时按 1D 后 HEAD 定稿）。
> 1E 正式动作：条目入 `data/proof_obligations/p1_2_proof_obligations.json` + checker
> `REQUIRED_OBLIGATION_IDS` / `REQUIRED_TESTS_BY_OBLIGATION_ID` 注册 + semantic digest +
> V99 floor + 自钉全链 reseal（走 close-kernel reseal SOP）。

## 条目草案（对齐现有 obligation 字段结构：id/title/evidence_paths/required_tests/v_findings）

- **id**: `PO-CERTIFIED-POWER-POLE-DOMINANCE-NORMALIZATION`
- **title**: certified 链在 routing FEASIBLE 后、CERTIFIED 返回前，必须对 solution 执行
  power-pole dominance 正规化并按 terminal 同语义复验；任何异常/复验失败 fail-closed 为
  UNKNOWN，不产 CERTIFIED。
- **statement 要点**（正文语句，1E 按 manifest 文风定稿）：
  1. 唯一生产点接线：`normalize_certified_power_pole_dominance` 在
     `_run_exact_binding_and_routing` 的 routing FEASIBLE 分支被调用，是 certified_exact
     CERTIFIED solution 的唯一出口正规化步；INFEASIBLE/UNKNOWN/cut/exploratory 路径不剪
     （防 whole-layout nogood 与 master 变量失配）。
  2. dominance 引理前提显式化：power_pole 不参与 binding/routing 端口责任；删除非唯一
     coverer 杆保持 coverage（每个原被覆盖 powered 仍有 coverer）、只释放格子不制造
     overlap、ghost/lex 值不变。
  3. 复验与 terminal verifier 逐条同语义（R1 coverage 保持 / R2 杆数≤powered 数 /
     R3 每杆为某 powered 唯一 coverer），并叠加 R4（required 下界只数 pose-optional 杆，
     对齐 terminal 的 optional_solution_counts 口径）与 R5（非杆 entry 逐 key 保持）。
     R2⊂R3 的鸽巢蕴含关系由测试锚定（R2-only 几何负例不可构造）。
  4. required>0 时不剪只复验；mandatory 杆不剪但参与 unforced 计算；ghost_pick marker
     双条件豁免（instance_id=="ghost_pick" 且 facility_type=="ghost_rect"），其余缺模板/
     未知 entry 一律 fail-closed（含 power_pole 自身模板缺失）。
  5. 调用链异常屏障闭合：wrapper required 源类型防御 + S3 调用点 try/except → UNKNOWN；
     异常不逸出、不崩 solve、绝不 mint CERTIFIED。
- **evidence_paths**（1E 按最终行号锚定）：
  - `src/search/benders_loop.py`（纯函数 + wrapper + S3 接线）
  - `src/search/exact_campaign.py`（terminal 语义参照 :1192-1253）
  - `src/tests/test_power_pole_dominance_normalization.py`
  - `docs/research/p1_3_batch1_design_20260710/02_batch1c_spec.md`（拍板记录）
- **required_tests**（14 个，名单已随 `3cc3cf4` 稳定）：
  ```
  test_t1_redundant_power_pole_is_pruned_and_non_poles_are_unchanged
  test_t2_minimal_covering_set_is_a_noop
  test_t3_pruning_iterates_to_a_deterministic_fixed_point
  test_t4_all_optional_poles_are_pruned_when_nothing_needs_power
  test_t5_mandatory_poles_are_never_pruned_but_affect_reverification
  test_t6_positive_required_count_skips_pruning_and_reverifies
  test_t7_required_layout_with_unforced_pole_fails_closed
  test_t8_malformed_pose_data_always_fails_closed
  test_t9_normalization_is_byte_deterministic
  test_t10_c1_certified_endpoint_returns_normalized_power_poles
  test_t11_legacy_witness_certified_endpoint_is_rejected_fail_closed
  test_t12_reverification_matches_terminal_r1_r3_semantics
  test_t13_normalization_failure_turns_feasible_routing_into_unknown
  test_t14_s3_certified_path_prunes_redundant_pole_without_mutating_input
  ```
  ✅ t11 更名已同步（2026-07-10 1D 终审期核实实名）：1D 按规格 S5 把 t11 改造为
  「certified 下旧编码被防御断言拒绝」的回归钉，原名
  `test_t11_legacy_witness_certified_endpoint_uses_same_normalizer` 已不存在。
- **v_findings**: 空起（新条目）。

## 1E 其余工作面备忘（非本稿范围，1E 规格书定稿）

1. C1 编码语义相关义务：并入 `PO-CERTIFIED-MASTER-DOMAIN-FAITHFULNESS` 追加 C1 表示条款
   （杆槽拆除/p_k 池/cov 通道/required 恰 N/池完整性 fail-closed）还是独立新 ID——1E 拍板；
   任务书 §三.5 允许两种，倾向并入（domain faithfulness 本来就管 master 编码忠实性）。
2. 1D 的 canonical env 收缩与 certified 防御断言进哪条义务：倾向并入
   `PO-CERTIFIED-MASTER-DOMAIN-FAITHFULNESS` 或 env guard 相关既有锚（checker V-needle
   已锚 env guard 结构，1E 核对是否需要正文级条款）。
3. F5 adapter TCB classification（1D 终审已落/将落）在 checker floor 的登记与义务文字对齐。
4. reseal 顺序照 SOP：JSON 条目+checker 注册同批 → source pins → semantic digest 不动点 →
   allowlist（若 strong-status writer 变动）→ checker 自钉最后。
