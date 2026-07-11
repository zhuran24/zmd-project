# cachy 老仓考古：B1 证据链与供电编码史（codex exec，2026-07-09）

> 材料源：cachy 老项目（`<repo-root>`，2026 年 5 月主战场=「原机」）的 117 张 memory 卡 + research 归档索引。
> 由 codex CLI 只读考古产出。上游问题：owner 拷问 B1 34× 证据可靠性（`00_design_decision.md` 附录三）。
> 附带勘察事实（主会话验证）：老仓其余六个 ghost 的 cuts_*.json 全空（仅 cuts_6x6 有 5 条）；campaign 检查点 final_status=UNPROVEN 零候选；老 CC 主会话转录已被 30 天清理，无备份。

## A. B1 假可行漏洞时间线（出处+短引）

- **Phase 0 的 53s/20.6s 数字不是完整端到端可行性，只是 master 级 power-feasible。**  
  `project_b1_phase0_go.md`：范围“不包括 `port_binding` / `routing / flow`”；数据是“49-53s OPTIMAL + corner 20.6s INFEASIBLE”。

- **“ghost 吃掉电杆仍 OPTIMAL”在 B1 Phase 0 代码路径里没有成立：pole pose 已按 ghost 过滤，coverer 为空会禁 pose。**  
  `poc_pose_bool_with_power.py`：`if any(c in forbidden for c in cells_tup): continue`；`无 coverer → 此 pose 不可选`。

- **所以 53s OPTIMAL 不是“供电 ghost 漏洞修补前”的数字；但它确实是“端口/路由责任边界修补前”的欠约束数字。**  
  `b1_pose_bool_phase0_20260517/README.md`：“prototype 范围”只含 `power_coverage`，不含 routing；`project_b1_phase1_findings.md`：“routing precheck front_blocked”。

- **Phase 1/2 继续确认 master+binding 快，但 routing 已报警。**  
  `project_b1_phase1_findings.md`：“master 52.9s OPTIMAL + binding 0.0s FEASIBLE”；“routing precheck front_blocked”。  
  `project_b1_phase2_production_land.md`：“master 53.3s OPTIMAL + binding 0.1s FEASIBLE”。

- **Phase 4 才把“假可行”的端口根因打明：master 不知道 port direction。**  
  `project_b1_phase4_routing_convergence.md`：“routing precheck `front_blocked` ~500-610 ports”；“pose-bool master 不知 port direction”。

- **Phase 5 发现三种补 cut 都过强/不收敛：把所有 port 当 active 是错假设。**  
  `project_b1_phase5_cell_cut_findings.md`：“3 种 cut 形式实测均 over-restrictive”；“master 不知道 binding 选哪些 port active”。

- **Phase 6.1 审计修正了错误诊断：不是只有 storage box port 可 inactive，而是任何 facility 都可能 inactive。**  
  `project_b1_phase6_audit_finding.md`：“任何 facility 的 port_cell 都可能 inactive”；“scope 放大：port_active BoolVar 给所有 facility”。

- **Phase 6 path-1 试图修补为 master 持 port-selection，但 scale 死。**  
  `project_b1_phase6_path1_dead.md`：“333K vars / 867K constraints”；“8w 300s UNKNOWN / 1w 600s UNKNOWN”；“架构层不可解”。

- **Phase 6 path-2 lazy demand cut 也死：master 能 OPTIMAL，但 cut 不约束 binding 选择。**  
  `project_b1_phase6_path2_dead.md`：“UNPROVEN 778s”；“binding port-selection 不匹配是 fundamental”。

- **B1 最终判死的精确理由：不是供电 53s 本身假，而是无法把 port/routing 可行性以可解规模放进 master，也无法靠 lazy cut 收敛。**  
  `project_b1_phase6_path1_dead.md`：“端到端 certified FEASIBLE/INFEASIBLE 未拿到”。  
  `project_paradigm_death_timeline_27_lever.md`：“Cut amplification 不够”“pose-bool master 表达力 limits”。

## B. 供电编码相关的历史罪证/死法

- **30GB 真凶是 coordinate master 的供电 witness 编码在 solve-time 膨胀，不是 build 存储。**  
  `project_30gb_real_culprit_power_coverage.md`：“cover_literals: 0”“witness_indices: 763”“solve-time propagation buffer 动态膨胀”。

- **当时的“cover_lit aggregate 死”是因为调研看错 production 路径：production 不走 table encoding。**  
  `project_30gb_real_culprit_power_coverage.md`：“cover_lit aggregate path = wrong source file”；“KILL cover_lit aggregate path”。

- **首解之墙被 Step D 精确锁到 `_add_geometric_power_coverage_constraints`。**  
  `project_2026_05_17_session_terminal_state.md`：“真瓶颈精确锁到 `_add_geometric_power_coverage_constraints`”。  
  `setpacking_prover_poc_20260517/README.md`：“skip_power=True 65.9s；skip_power=False 30 min UNKNOWN”。

- **Lazy Power Completion 证明：把 coverage 移出 master 会快，但 cut 收敛失败。**  
  `project_l16_lazy_power_completion_phase0.md`：“81.8s OPTIMAL”；“134/220 powered instance 无可用 pole”；“134→133 stuck”。

- **HiGHS/LP-MIP 路径证明：显式 dense linear power matrix 会炸内存。**  
  `project_highs_rewrite_blocker.md`：“HiGHS full 42.15 GB”；“LP-MIP 对 dense linear constraint 不适合”。

- **paradigm death 里供电相关死法：L16 属 Class B，B1 path2 属 Class A，augmented master 属 Class D。**  
  `project_paradigm_death_timeline_27_lever.md`：“L16 Lazy Power Completion”；“B1 Phase 6 path-2”；“Master augmentation 撞 scale 墙”。

## C. 对当前批1（供电编码手术）的直接校准价值

- **当前 linear cover_lit 方向有正证据：B1 pose-bool 用 `x <= sum(pole coverers)` 跑出 49-53s。**  
  `project_b1_phase0_go.md`：“power coverage 约束: ~270K（每 powered pose 一条 linear）”。  
  `b1_pose_bool_phase0_20260517/README.md`：“pose-bool form 让 power_coverage 直接可解”。

- **但必须验证当前代码真走新编码，不要重演 5/15 看错 source path。**  
  `project_30gb_real_culprit_power_coverage.md`：“production 不走这个”；“wrong source file”。

- **ghost 条件必须直接进入 cover domain：pole pose 被 ghost 吃掉后不能留在 coverer 集。**  
  `poc_pose_bool_with_power.py`：“只保留在 pole_vars（即 feasible）里的”；`state_machine_v2.md`：“ghost_rect changes → power_cover_invalid = True”。

- **如果 cover set 为空，正确行为是禁 facility pose，不是靠 witness 后验失败。**  
  `poc_pose_bool_with_power.py`：“无 coverer → `model.Add(x_var == 0)`”。

- **只看 build/RSS 不够，必须看 master.solve status、branches/propagation 和首解。**  
  `project_30gb_real_culprit_power_coverage.md`：“build-time peak 3.10 GB vs solve-time 30 GB”。  
  `v8_anchor_slicing_smoke_20260516/README.md`：“build -92%，但 solve 阶段没改善”。

- **不要把 B1 的 53s 当端到端可行性指标；它只校准供电 master 首解。**  
  `project_b1_phase1_findings.md`：“routing precheck front_blocked”；`project_b1_phase6_path1_dead.md`：“certified FEASIBLE/INFEASIBLE 未拿到”。

## D. 当时会话终态：项目 5 月底停在哪、为什么转移

- **5/15 停在“RAM 不是首解瓶颈”。**  
  `project_2026_05_15_ram_session_misdirected.md`：“workers=8→1 verified 30→12.19 GiB”；“14h trial 51 new candidates 全 UNKNOWN”。

- **5/16 停在 GPT 三条轻量算法路全死。**  
  `project_2026_05_16_session_final_state.md`：“v8 / v10 / L14 全 verdict 死”；“严格性 + 算法层穷尽”。

- **5/17 停在 power_coverage 被锁定，L16 lazy 失败，用户决定走 B1。**  
  `project_2026_05_17_session_terminal_state.md`：“Step D power_coverage 锁瓶颈”；“用户决策走 B1”。

- **5/22 后主线从 B1 单点修补转成 B Design v2 cut framework。**  
  `project_phase0_b_prep_progress.md`：“9 family + cut_lifecycle v3.2.2”；“Phase 1 编码 GO”。

- **5/27 最新本机记忆终态：Phase 1.2/F3 special-case 已收口，下一步 P1.3A 从 master 起。**  
  `project_phase_1_2_progress.md`：“下一步 P1.3A 主体设计”；“spike 分支 throw-away，不 cherry-pick”。

## E. research 归档中值得后续深读的目录清单（相关度排序）

1. `b1_pose_bool_phase0_20260517/`  
   B1 全生命周期核心目录；README 含 Phase 0、Phase 6 path-1、storage-box PoC 结论。

2. `phase0_lazy_power_completion_20260517/`  
   lazy power 的失败原始数据；“81.8s OPTIMAL”与“134→133 stuck”都在这里。

3. `setpacking_prover_poc_20260517/`  
   Step D 锁定供电首解墙的最清晰实验归档；skip/full 对比最有校准价值。

4. `p3_b_design_v2_20260521/`  
   后续 power_hitting_set / power_grid_reach / ghost-conditioned power cover 的设计源。

5. `paradigm_search_review_v12_with_code_20260520/`  
   24 lever dead + B1 dead_paths 总包索引，适合查“这个想法历史上是不是死过”。

6. `v8_anchor_slicing_smoke_20260516/`  
   master 性能误判样本：build 优化有效但 solve 不改善。

7. `v10_witness_preflight_smoke_20260516/`  
   witness 类方案的前提错估样本，避免把“有 witness”误当当前可用首解。