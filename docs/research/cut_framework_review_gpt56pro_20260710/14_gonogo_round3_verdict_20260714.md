# 14 — go/no-go round-3 + 上界墙裂缝(2026-07-14→15):必要条件 sound,且对抗席挖出它被自我低估的上界价值

> **历史失效标记（Batch 4，2026-07-18）**：本文的 138→104、83–85
> front 地板、PASS/FAIL 统计及旧必要条件实例均已撤销或待重验（RND-04/
> RND-05）。逻辑模板与实测数字必须分开；详见
> [历史重判附录](../front_offset_incident_20260718/01_historical_rejudgment_addendum.md)。

> 承 doc 13。工作流 `wf_d7453509-15d`(4 Work[路①lift-scout claude+codex / 路②witness构造器 claude+codex] + 3 对抗 Verify),zero-sealed 只读,~80min,7 席 0 error。harness 在 `scratchpad/spike_round3/`;journal 在 `subagents/workflows/wf_d7453509-15d/journal.jsonl`。

## 0. 一句话结论(改写 round-2 的"上界是硬墙")

**round-2 说"上界没有便宜证书、是硬墙"——round-3 的对抗验证席自己推翻了这句:路①的 `front_clear >= routing-visible demand` 必要条件被双模型独立核实为 sound(数学蕴含、无反例),而按其自身 soundness 论证的逆否命题,把它上收进 master 后若判 INFEASIBLE,就是一张合法的 certified-infeasible 上界(最优性)证书——这恰恰是 round-2 断言不存在的东西。** 路②的实证(front 地板 83-85、body 重排撑爆走廊预算)是"front_clear 在本实例上很可能真不可满足"的旁证。但**决定性实验(建一个紧凑的 front_clear-lifted coordinate master、在小锚点上真跑一次看 FEASIBLE/INFEASIBLE)两路都没做过**——这是 round-4。

## 1. 四席 Work 结论

| 席 | 轨 | verdict | 要点 |
|---|---|---|---|
| claude opus48 | 路① lift-scout | **alive** | `front_clear[(cell,dir)]=1 iff in-grid 且非 body 占用`;per-facility `sum(front_clear over 候选端口 cell) >= 排除 routing_free_sink 的可见需求`。是 ∃-binding per-facility 松弛,非 620 全端口上收 |
| codex | 路① lift-scout | undetermined | codex 进程被 StructuredOutput 强制打断前未产出判定,如实标 undetermined(不编造) |
| claude | 路② 构造器 | stuck_at_front | 138→地板;换 pose/binding 不动 body 只到 83-138;body 重排撑爆走廊预算 |
| codex | 路② 构造器 | stuck_at_front | 138→**104**(92 body/outgrid+12 connector-cross),72 端口仍 connector-body 重叠;joint pose+binding CP-SAT OPTIMAL=104 是固定 body 下真地板 |

## 2. 三席对抗 Verify(关键)

### Verify 11 — 路② witness(refuted=False,clean)
亲手 stdlib 重算(环境断链无法跑 ortools,改做更强的纯几何重算):从 candidate_placements.json 原始 pool 按 pose_idx 重建占用集、逐谓词重算 → front_blocked=104 **逐位对上** producer;overlap 0、ghost 0、266/266、power 220/0;`front_is_zero=False` → 无 witness。确认 disc=0 是 front 早退空值签名(routing_subproblem.py:491-509 早退,连通段 511-627 从未进入),非连通通过;非 re-solve 作弊、未铸强状态。

### Verify 13 — 路① front_clear soundness 专项(codex+sonnet5 双独立,refuted=False,severity=concern)
**必要条件本身 sound、无反例、按证明结构也不太可能有反例(不是 fatal)。** 但支撑"alive 可低风险落地"的三根支柱都有实证缺口:
1. **storage cross-pose 扩展是死代码**:protocol_storage_box 全 4624 pose 物理端口=0,generic input 走 3 个无坐标 virtual/routing-free slot;若真启用"aggregate front-clear >= 需求"会变 `0>=2` 恒假、错拒 canonical wireless storage(test_wireless_sink_binding_semantics.py:96 证 box binding FEASIBLE+port_specs=[] 是对的)。**须整体删除、用既有 box-count 下界代替**,不是"已实现机制"。不污染 219 fixed-op 主条件。
2. **"coordinate master 已有 channel、紧凑性达标、不撞墓碑"测错了对象**:master_model.py:4694-4706 `build()` 在 exact_mode 下提前 return,`z_vars`/`_populate_cell_occupancy_terms`/`_add_port_clearance_constraints`(4888)全在 return 之后的 **exploratory-only ELSE 分支**;`exact_coordinate_master.py` grep `z_vars` 零命中(纯 interval AddNoOverlap2D)。→ 18,056 那个紧凑数字量的是 **pose_bool 离散池**,不是真正要承载约束的 coordinate 默认 master。**朴素移植 coordinate = 29,417,552 vars**(codex+sonnet5 独立算出同一数、超 2.24M/32G 墓碑)。且 pose_bool B1 范式家族已被历史归档为 dead path(333K vars/867K constraints/600s UNKNOWN)。**但不到 fatal**:MFE relative-geometry table 原型(2699 vars/3366 constraints)证明这类相对几何表能做得很小,估计紧凑 coordinate 编码可到 ~15K vars/17–19K constraints——但这是**全新工程 + 生产规模 build-only 审计**,不是"一行 fix"。alive 文案显著低估了这步难度。
3. **"塌缩死循环"收益被高估 + 新不完整性**:在最优 incumbent(joint_mode104)上重算 219 设施 front_clear 通过率 = PASS 163(74.4%)/FAIL 56(25.6%),比 b0_4r 的 216/219 fail 乐观得多。但 codex 挖出关键不完整性:**capacity 条件只保证"存在干净候选子集",不强制 binding 去选它**(反例 `grinder_fine_buckwheat_004`:capacity 通过,但 binding 选中的端口 front 被别人 connector 占)。即约束落地后 binding↔routing 逐点 nogood 循环未必真终止,除非额外把 master 选出的干净几何传给 binding、或把 env-gated 的 RAB-SEP filter 提升为 certified 默认。**——注意:此不完整性只影响下界/塌缩循环方向,不影响上界 INFEASIBLE 方向(见 §3)。**

### Verify 12 — 整体对抗(codex 未按时完成,转发者亲手核,refuted=True,severity=concern)
- 亲手证伪路①一条标"已验证"的断言:**"pose-bool Step 3 uses RAW profile slots、需减 routing_free_sink"为假**——真实 Step 3(`_routing_visible_profile_demands`→`_profile_port_demands`:337)**已经**减掉 routing_free_outputs;路①引用的行号 255-330 也错(真代码 ~630-725)。根因:路①的 frontclear_final_opus48.py 根本没 import pose_bool_exact_master.py,是自己重实现了一遍需求计算、把自建版本的(假想)问题错当成对真实源码的诊断。且真实 `_profile_port_demands` 的 generic_output 还依赖 `_generic_output_slots_are_globally_saturated` 等**跨设施全局条件**,比路①"纯 per-facility 局部"复杂——紧凑性论证在 generic-output 上可能不再严格局部。
- "already deployed on certified binding path" 省略了它本身也 `EXACT_B1_ROUTING_AWARE_BINDING` env-gated。
- **点9(转发者从路①自身证据链推出、路①完全没讨论的关键推论)**:路① soundness = "True-feasible ⟹ front_clear-satisfying"(其 groundtruth Test 1 = 0 反例经验支持)。**逆否命题**:若把 front_clear>=demand 作硬约束叠进 master(与 non-overlap/ghost/power 一起)后返回 INFEASIBLE,则合法推出"不存在真正可行布局" = **一张合法的上界(certified-infeasible)证书**——与路① SCOPE 段自称"does NOT close the upper bound"**相反**。路①既没讨论也没测过"body 作自由变量 + front_clear 作硬约束"跑一次真 solve(它的 COLLAPSE 只是在已固定的历史布局上数当下有多少设施违反)。而路②旁证(固定良好 body 下 front 地板 83-85、body 重排撑爆走廊)强烈提示"front_clear 对全部 219 设施同时可满足"在本实例上很可能就是不可行——若真如此,lifted master 跑出来是 INFEASIBLE = **恰好是那张上界证书**,不是路①说的"无上界价值"。

## 3. 综合定论:上界墙裂开一条待验证的缝

- **路① 的 front_clear >= routing-visible-demand 是真必要条件、sound(双独立、无反例、数学蕴含)。路①没被杀。**
- **最大收获**:对抗席自己推导出——**front_clear 上收进 master 若 INFEASIBLE = 合法上界证书**。这直接翻掉 round-2 的"上界没有便宜证书"。且**上界方向比下界方向更干净**:Verify 13 的不完整性(capacity≠binding选干净)只伤"FEASIBLE→拿witness"的下界方向;对 INFEASIBLE 方向,松弛仍不可行就是有效证书,与下游 binding 耦合无关。
- **代价 / 待解**:①真正紧凑的 coordinate 编码是全新工程(朴素移植 29.4M 撞墓碑;紧凑编码理论上可 ~15-19K、MFE 原型佐证,但需 build-only 规模审计);②storage 扩展死代码须删;③必须保证紧凑编码是"忠实、不比 live master 更严"的松弛(否则 INFEASIBLE 是假证书——见 [[projection-must-mirror-live-master-not-stricter]]);④INFEASIBLE 须能被独立 recompute-check(I1 方向,现 reverifier 只确认 binding-INFEASIBLE、对 routing-exhaustion 保守 UNKNOWN,需新的 single-bounded master-UNSAT reverifier)。
- **决定性实验(round-4,zero-sealed,不跑 60G prod master)**:建一个紧凑的 front_clear-lifted **coordinate** master 独立原型(266 真 body + 小 ghost 锚点 7×7 + front_clear grid-cell channel + per-facility >=可见需求),先 build-only 规模审计(vars/constraints/RSS,必须远低于墓碑),够紧凑再在小锚点上真跑一次 → FEASIBLE(下界线索)/ INFEASIBLE(上界证书候选)/ UNKNOWN。对抗验证专攻:构造"真可行却被编码拒"的反例(击杀证书)、best_bound 真实性、编码忠实性(不比 live 更严)。

## 4. 质量与诚实边界

7 席 claude+codex 双模型独立 + 3 席对抗验证;对抗席对路①"alive"做了逐行源码核对,发现并证伪一条标"已验证"的具体断言(RAW slots caveat)+ 行号错 + 测错对象的紧凑性数字——**"alive"的必要条件核心为真,但其落地叙事有实证错误,已在本文逐条订正**。全程 zero-sealed 只读、未跑 master/main.py、未铸强状态。环境事实:`.venv/bin/python3.13` 断链(07-15 清盘删了 interpreter_ab 目标),ortools 有效解释器 = `.venv-uvbolt-backup/bin/python3.13`(9.15.6755)。结论是研究判读,非 certified 结果。
