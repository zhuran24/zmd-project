---
name: p1-3a-design-phase
description: "2026-05-30 接手后首个 design phase — P1.3A 主体 (真 PoseBoolExactMaster + cut framework step_8 集成) 走 N=8 并行 opus 设计 + main merger. 关键: LBBD loop/桥/nogood 通道/replay 已落地在跑, P1.3A 只缺 src/cuts/lifecycle.py:1005 step_8 桥; 收敛是几何/paradigm 性质只能 Linux multi-anchor falsify; P1.3A 在 Windows 只 close soundness/termination/不-stall + 安全机制; 范围收窄 F1-only, 别 fold 9-family 收敛. 设计产物 docs/research/p1_3a_master_integration_design_20260530/ (DESIGN_BRIEF + 8 slant + P1_3A_MERGED_DESIGN + step0) **untracked, Windows 仓库已丢, 结论仅存本 memory 文本** (见正文顶部警告)."
metadata: 
  node_type: memory
  type: project
  originSessionId: ca5783d1-e3be-4591-8cfd-4ede5ed83635
---

> **本条 = P1.3A 设计阶段的记录** (N=8 设计产物 + GPT Pro verdict + Step 0 gate 结果)。项目「当前 phase/交接状态」的单一 living 源是 [[windows-ninth-review-pending]] (per [[memory-currency-protocol]]); 本条只补设计细节, 不作现状真相来源。

> **⚠️ 文件丢失警告 (2026-06-02 审计)**: 本条引用的 `docs/research/p1_3a_master_integration_design_20260530/` 整个目录 —— `DESIGN_BRIEF.md` / 8 份 slant / `P1_3A_MERGED_DESIGN.md` / `gpt_pro_verdict_20260530.md` / `GPT_PRO_AUDIT_P1_3A.md` / `step0_cheap_gate/`(`step0_prototype.py` / `test_step0_gates.py` / `STEP0_RESULTS.md`)—— **全部 untracked, 没进 repo.bundle, Windows 仓库里不存在** (git ls-files/status/ls 均空; 仅可能留在原 Linux 机)。**设计结论本身保存在下方本 memory 文本里**(8 路结论 / GPT 细化 / Step0 机制都在), 但**别去仓库里读那些文件 —— 不在**。要原始文件得回 Linux 原机取或重跑。下文凡 "读 X.md §N" "X.py 621 行" 类指引, 都指这些**已丢文件**, 当历史记录看, 别当可读路径。

2026-05-30 接手后第一个 design phase。用户选了 N=8 并行设计(per [[design-phase-n-parallel-agents]])。main 当 merger。

**产物**: `docs/research/p1_3a_master_integration_design_20260530/` —— `DESIGN_BRIEF.md` + 8 份 `<slant>_design.md`(correctness/throughput/adversarial/integration/simplicity/rollback_safety/observability/historical_paradigm_context)+ `P1_3A_MERGED_DESIGN.md`(merger 合成 + 实施蓝图 §9 + 给用户的决策清单 §10)。

**8 路一致结论**:
- LBBD 外循环 + `add_benders_cut` 桥 + `_add_exact_persisted_nogood` nogood 通道 + fail-closed replay **已落地在跑**; P1.3A 真正缺的只有 `src/cuts/lifecycle.py:1005 step_8`(NotImplementedError stub)。brief「设计整个 loop」高估。
- **收敛只能 Linux multi-anchor campaign falsify**(死路全死在 multi-anchor 0/8); P1.3A 在 Windows 只能 close soundness + termination + 不-stall + 5 风险的安全机制。**UNPROVEN 是合法终态**(historical 提醒, 对齐 06 doc sound≠converge)。
- 范围收窄: **P1.3A = F1 单 family 在 real PoseBool master 单 anchor 驱动收敛、sound/单调/不振荡**; **别把 9-family 收敛证明 fold 进来**(前 6 paradigm 撞死的墙, simplicity verbatim 划界, per [[main-merger-scope-creep-bias]])。

**头号架构决策(cut 强形式 vs nogood 弱形式)**: merger 裁决走**强形式分 family** —— F1/F6/F9 = 对 master pose 变量的 **domain-wise 线性 capacity 约束**(需扩 `MasterModelLike` 加只读 `enumerate_poses_in_region`, 不改 var basis, 守 root cause 1); F2/F4 借已验证的 PCR-CUT belt oracle `add_patch_routing_core_cut`; F8 **defer**(structural-disconnect 判据缺、最弱环, 降 conditional 会引非单调=L16 振荡); pose-presence nogood 作 sound fallback(F3/F5/F7 本就此态)。依据: pose-presence nogood 正是 core≈1 切≪1% 害死前 6 paradigm 的弱形式(historical), correctness 的「evaluator 语义⟹约束 domain-wise」lemma + GATE2 保证强形式 sound 落地。

**v25 实测 sizing 基线(lowering 预算硬约束, 2026-06-02 spike 产出, 别随 handoff transient 过期丢)**: compact (witness/no-good) lowering **全 9 族 100K 都便宜** (~1-3 MB)。expanded (全 pose-overlap) lowering 必**按约束类型分字节预算** —— 实测 OR-Tools 9.15: 线性 `sum<=k-1` ~**3-4 B/term**, `AddBoolOr` no-good ~**10-11 B/term** (贵 ~3×, 见 [[cp-sat-no-add-lazy-constraint]])。term 量级(fixture 尺度, LSB-correct): region 大池子 ~264 / cutset ~173 / **F9 window scoped max 784 / all-type UB 3341** / F4-separator 5429。cap 按 **max/p99 跨所有族**(不止 F1/F9)。**⚠️ v25 第四轮外审 (A-F1) 关键修正: 上面这些是 type-pool pose 数, 不是真 master 的 concrete literal 数**。真 master 按 `(facility_type, operation_type)` group×pose 建变量 (266 instances → 19 group, mfg_3x3=8/mfg_5x5=4/mfg_6x4=5 group), concrete 数 ≈4× type-pool (81,795 → **325,747**); group 展开后 F9 784→**11,644**, F4 5429→**20,157**, 满 mfg 池→295,700。**所以 cap 的输入必须是真 translator 在 group/template/optional 展开后发出的 concrete literal vector 长度, 不是 type-pool 数; 别把 3341/5429/16-18K 当真-master 上界**。**对本设计的含义**: 强形式 F1/F6/F9 = domain-wise **线性** capacity 约束(~3-4 B/term, 便宜端, 是好消息) —— 但 capacity 约束的 term 数也要按 group-expanded concrete poses 数, 不是 type-pool; pose-presence nogood fallback 若编码成 BoolOr 贵 3×, 优先 `sum<=k-1` 线性编码。纠正前"F1/F9 大池子 → 1.9GB blow-up"是 MSB bitset bug 假数字(已废), 真实 fixture 尺度不爆。详 [[windows-ninth-review-pending]] v25 块。

**关键安全机制(8 路共识)**:
1. step_8 **两阶段 commit**(propose 纯函数验→commit 才碰 model)+ **apply-epoch rebuild barrier** —— 解决 adversarial 发现的 soundness 洞: quarantine 只动 CutStore, 但 `add_benders_cut` 已把约束 Add 进 **append-only model**, 收不回 stale/坏 cut。
2. **GATE2 translation-soundness gate**(replay 之外第二道 fail-closed); 新 soundness 工作 100% 在第五验(invariant↔master)。
3. **content-keyed dedup**(现只按 cut_id 去重, master swap-1-pose 绕开旧 cut → 误当进展; 严禁跨 instance)。
4. **stall 探针**(连续 3 iter bound-gap 改善<1% 且 active cut 仍增)+ **oscillation detector**(solution_hash/front_blocked_port_count 2-周期)→ 作第 4 条 revert criterion(现 14 §14.3 三条看不见"健康 OPTIMAL+持续加cut+安静烧168h"); 只 relabel UNKNOWN 绝不伪造 certified; max_iter 耗尽单独 bucket(别误判去加 F10)。
5. env `EXACT_B_DESIGN_V2` **AND** `EXACT_USE_POSE_BOOL_MASTER` 默认 **OFF** + byte-equality 焊死 env-off 等价 + 红线不许改 step_7 dispatch/cut 链优先级。ramp 按回滚爆炸半径 F1→F6/F9→F2/F4→F3/F7/F5→F8。

**throughput 纠正**: solve wall 是"cut 把解空间逼到多接近 96% 几何死结边界"的函数、不是 cut count 函数; 09 §12.2 hot-path 三件套对 evaluator 零 ROI(CP-SAT C++ 不回调 Python evaluator)= micro-opt 螺旋, P1.3A 不做; warm-start(incumbent-as-hint)latency ROI 最高。

**待用户 phase-boundary 决策(§10)**: (1) 接受 F1-only 收窄? (2) 接受强 cut 分 family 方案? (3) 现在进 Step 0 cheap gate 落代码 vs 先等 v22 GPT 九审 GO? (4) F8 defer 可接受? **当前停在等用户这 4 个决定, 未动任何代码。**

**Why**: 接手后首个实质设计推进, 8 路并行 + merger 结论 + 头号架构决策, 非显然且决定 P1.3A 走向。
**How to apply**: 实施顺序(原在已丢的 `P1_3A_MERGED_DESIGN.md` §9, 现仅凭本 memory 复述): Step0 Windows cheap gate → F1 step_8 → benders hook → Windows verify → [GATE] Linux 收敛; 收敛验证 defer Linux; 别 fold 9-family 收敛。(原始 merged design 文件不在仓库, 见顶部丢失警告; 真要细节回 Linux 原机取或按本 memory 各 § 重建。)relate [[windows-handoff-env]] [[main-merger-scope-creep-bias]] [[paradigm-phase0-cheap-gate]] subproblem-vs-augmented-master-default。

## GPT Pro 设计审 verdict (2026-05-30) — GO(收窄)+ 硬细化

把 P1.3A 设计的入口 brief(`GPT_PRO_AUDIT_P1_3A.md`,de-primed 版)交 GPT Pro 设计审。verdict 全文存档 `docs/research/p1_3a_master_integration_design_20260530/gpt_pro_verdict_20260530.md`,折进 `P1_3A_MERGED_DESIGN.md §0.5`。

- **GO 范围 = Step 0 cheap gate + F1-only "lifecycle close"**(改名,不叫 P1.3A close)。largely 认可方向(F1-only/强 cut/F8 defer/Step0 先/等 v22 全对)。GPT 是**设计层审**,声明没看仓库源码、不能验 code-cleanliness。
- **关键细化(都已折进 §0.5)**: ① **rebuild barrier 必须从 base model + active cut IR 全新重建、丢弃所有旧 CpSolver/proto/hints/assumptions/callback/bound 缓存**(不能只追加,否则 quarantine 的坏 cut 仍在 live proto 剪合法解); ② **propose 阶段类型上拿不到 CpModel**(`propose(cut,frozen_snapshot)->CutIR|Reject` / `commit(CutIR,model)->Handle`); ③ **新选项 guarded cuts + assumptions**(我们漏的:每 cut 加 guard literal, active set 由 assumptions 控, quarantine 清 guard, final 仍 rebuild-from-base)—— 不是 AddLazyConstraint; ④ **`enumerate_poses_in_region` 必须绑 `pose_universe_hash`**(facility/registry ver/anchor scope/objective ctx/filters/frame/translator ver), content-dedup key on 它 —— P0 不是 P1; ⑤ **GATE2 两层**(translator lemma + **独立 replay** 不用 prod translator + 小网格 exhaustive 枚举); ⑥ **F6/F9 系数 = min over compatible completions**(under-approx),严禁用当前 routing 实际用量(否则 conditional demand 当 unconditional → 剪合法解); ⑦ **F2/F4 PCR-belt 只在 oracle scope==master scope 时 sound**; ⑧ **capacity cut 正确命题 = ∀x∈原可行解 C_R(x)**,不是"当前点 infeasible"。
- **cleanliness Layer-2 警告**: `HEAD clean+414 tests` 不足; 真要防"假 cut 剪更优解后 final cert 仍 pass"; 补**假证攻击测试** 5 条(inject_unsound_cut_then_quarantine_must_recover / same_bad_translator_replay_must_not_be_sufficient / final_cert_must_include_active_cut_manifest / anchor_scope_hash_mismatch_must_fail_closed / unknown_status_must_not_emit_certified)。
- **收敛**: 形式化确认**只能证无用的 |X| 弱 bound,practical 收敛 UNPROVEN、只能 Linux multi-anchor campaign falsify**; campaign 改测量化 amplification 指标(不是 pass/fail)。
- **NOT-GO**: 现接 F6/F9 到 certified path / 现做 F8 / 宣称全 instance 收敛 / 同 translator replay 当 Layer-2 证明 / 只靠 CutStore quarantine / 只用 HEAD+414 当 cleanliness。
- **Step 0 cheap gate 扩成 8 项**(均单机可跑): No-mutation / Bad-cut-quarantine / Rebuild-identity(4 hash) / Guard-activation / F1-exhaustive-tiny(6×6,8×8) / Anchor-mismatch / Semantic-dedup / UNKNOWN-bucket。
- GPT 一句话: 核心不是"补 step_8", 而是把 cut 升级成**"可独立重放/可开关/可重建/可证不剪合法解"的证据对象**。
- **下一步待用户定**: (a) 是否把全包(merged+8 slant+源码+death baseline)再喂 GPT 做深一层 code-level 审(GPT 这轮只看了 brief)? (b) 现在开 Step 0 cheap gate 实施(GPT GO 了、可逆、不依赖 v22)还是连 Step0 也等? step_8 实质代码仍等 v22 九审 CLEAN GO(D4)。

## Step 0 cheap gate 结果 (2026-05-30) — 8/8 PASS, main 独立复核

用户拍板"全做"。起 opus 子代理实现 Step 0 为 **standalone 原型 + 12 测试**(`docs/research/p1_3a_master_integration_design_20260530/step0_cheap_gate/`:`step0_prototype.py` 621 行 / `step0_f1_bridge.py` / `test_step0_gates.py` / `STEP0_RESULTS.md`)。**真跑 OR-Tools 9.15/Py3.13 = 12 passed 0.33s;main 独立复核(重跑 + 通读 prototype/test 代码 + 看真实证据数)= gate 真咬、非 vacuous;`src/` 零改动(git 确认)。**

- 8 gate 全 PASS + negative-control + bridge。证据:gate2 with_bad=INFEASIBLE→quarantine+rebuild→OPTIMAL + proto hash 真变 + control(假 append-only 仍 INFEASIBLE 证明是 rebuild 起作用);gate5 6×6=13feasible/0unsound、8×8=21/0、teeth=4、verifier 抓到注入 unsound cut(3 处);negative-control propose 对非违反点 Reject(not_f1_violation);**bridge 真跑 src_available=True,production `compute_static_capacity`=3 == standalone cap_R=3**。
- **确认**:F1 capacity cut domain-wise soundness 小规模成立;rebuild-from-base / 两阶段 commit(propose 类型上无 model)/ guarded cuts(only_enforce_if+assumptions)/ universe-hash dedup / UNKNOWN bucket 机制都 work。**无设计前提被证伪。**
- **main review 追加 1 条 production invariant(给 step_8)**:guarded-cut 下 final certified solve **必须 hard-add active cuts 或 assume-true 全部 active guard,绝不留 free guard**(否则 solver 设 guard=false 让 cut 静默失效=unsound;gate4 "inert=OPTIMAL" 即此路径)。step_8 要带 `certified_solve_never_leaves_active_guard_free` 测试。已折进 `P1_3A_MERGED_DESIGN.md §0.6`。
- **仍 defer Linux**:收敛/amplification(#1)、真 70×70 universe vs replay pose_domain 一致性、大 proto str() hash 稳定性、数千 cut+30-47GB rebuild 成本、F6/F9/F2/F4/F8。
- **状态**:Step 0 GREEN,设计 soundness 前提小规模全验。**production step_8(F1-only)仍按 D4 等 v22 九审 CLEAN GO 才落代码。** 未 commit(所有产物 untracked)。
