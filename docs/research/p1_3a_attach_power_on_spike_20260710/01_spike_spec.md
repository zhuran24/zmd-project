# P1.3A attach 通电 spike 规格书（主会话亲写定稿，2026-07-10 夜）

> 全项目唯一研究级风险的实测批（roadmap §1c/09 号计划 §P1.3A）：cut 体系接上后
> 能否及时变成有效 master 约束、收不收敛没有理论保证。exploratory 下通电，
> certified unsafe-map 禁用不动。HEAD 基线 `5e7c760`。

## §0 唯一问题与 GO/NO-GO（09:15,27-28）

CP-SAT Python 路径能否在预期时机把 cut 变成有效 master 约束？
**GO = prod-scale（266 instance + 目标 ~10K cut）端到端 master cycle 跑通，
wall-clock 退化 <50%**（对照=同参数 attach-off 基线，不是 M5 的 506s master-only）。
NOT GO → paradigm 层风险上桌（09:30-32，退路见 roadmap §4 L11）。

## §1 前置状态（2026-07-10 全绿，当日凑齐）

1. step_8 F1/F5/F6/F7 落地（M3）+ 逐族阶梯（M4）；F8 退役、其余族 fail-closed。
2. 通电前修复批 `68b4557`：F1 BState ghost 轴反置（soundness 级）/F2 scope 全 map
   严格相等/F3 step_8 入口完整性纵深——三 repro 翻绿。
3. **硬性前置①（sizing verdict §3.1）content-addressed literal 复用：M3-2 已落地**
   （exact_coordinate_master.py:776/:7782，p_k 即 content-addressed presence literal）。
4. **硬性前置②（verdict §3.2）active cut 预算：M4-A 已落地**（benders_loop.py:946
   `EXACT_CUT_FRAMEWORK_ATTACH_BUDGET=2000`，stop-emitting 形态=CP-SAT 不可撤约束
   下唯一 sound eviction；:8054 docstring）。
5. prod-scale master 可出解（M5 归因判决：6×6 w6+automatic/probing1/symmetry1
   506s OPTIMAL；资源条款 42G 帽+20G swap `b25ba1d`）。
6. 通路现状：`EXACT_CUT_FRAMEWORK_ATTACH` env 非 false 即开（:7838），certified
   unsafe-map 拦截不动；`_maybe_attach_framework_cuts` 双接线点（:6323/:7493）。

## §2 实验序列（主会话执行，单发铁律）

- **E1 基线**：exploratory 6×6 LBBD 端到端，attach off。资源条款=42G 帽+20G swap+
  w6+原型参数（M5 第四/五刀同款）；RSS 1s 采样+VmHWM+VmSwap（SOP）。记 wall/内存/
  LBBD 迭代数/终态。
- **E2 通电**：同参数 + `EXACT_CUT_FRAMEWORK_ATTACH=1`（预算 2000 默认）。观测：
  wall 退化 %、`cut_framework_attached` 计数、拒绝 taxonomy 五桶、内存曲线对照、
  **解语义一致性**（exploratory 也验：E2 若出解，其 layout 过与 E1 相同的独立
  校验路径；attach 只应剪支不应改变可行解集）。
- **E3 预算抬档**（E2 达标才跑）：抬 attach 预算扫 5K/10K 档看 proto 劈叉曲线
  （literal 复用后 sizing verdict 预言的量级改善实测）。改动面=预算常量 env 化
  （`EXACT_CUT_FRAMEWORK_ATTACH_BUDGET` 加同名 env 覆盖，certified allowlist
  **不加**——exploratory-only knob 走 deny-unknown 天然拦截即可；此为本批唯一
  生产代码改动，几行）。
- cut 流量前提核查（E1 顺带）：6×6 LBBD 每 attempt 真实产出的 cut 量级未知——
  若天然到不了千级，E3 改造成合成注入（复用 sizing spike 的 m1_*.py 负载形态）。

## §3 三硬门采纳度拍板（TRIAGE §3，5.6 复审建议）

spike=exploratory 实验非生产通电，三硬门是 production integration 的门：
1. 原子封口（RFC-001）：**spike 不做**。F3 已落的 step_8 入口 integrity 纵深+
   接线层 fail-closed（c7cd6a0）构成 spike 级安全面。
2. F5 独立 verifier（RFC-002）：**spike 保持 F5 shadow/不 mutate master**（现状），
   通电族=F1/F6/F7。
3. ledger+dedup+epoch（RFC-003）：**spike 豁免**——单 epoch 单 master 场景，
   ghost conditioning（M4-A）已处理 anchor 切换退役。
三条全部记入 GO 后 production integration checklist（不因 spike 通过而消失）。

## §4 验收清单

- [ ] E1/E2 完成且 E2 wall 退化 <50%（GO 线）；E2 attach 计数 >0（真通电证据）
- [ ] 拒绝 taxonomy 无 integrity 桶异常（有=修复批回归，立停）
- [ ] 解语义一致性核验通过
- [ ] E3（达标时）：预算 env 化小改过 preflight+慢 lane（benders_loop 是钉面→reseal）
- [ ] evidence 文档 02_spike_evidence.md（曲线+判定）；GO/NOT-GO 判词写明
- [ ] 全程单发铁律+树冻结+解释器病 SOP（崩=coredumpctl 定性重跑）

## §5 分工

实验设计+规格书=主会话（本稿）；E1/E2 执行+判定=主会话（prod-scale 长跑+终审）；
E3 预算 env 化小改=codex（几行+测试）；E3 后 reseal=主会话。审查=E3 改动走
opus+codex 双审（纯实验记录不需审）。

## 附：E1 执行记录（2026-07-10 夜，基线首跑失败与重设计）

- E1 首跑（wrapper 全套=jemalloc no-decay 注入）：**exit 137 OOM @21.5min**，死状
  RSS 39G+HWM 41G+**swap 顶满 20.00G**；且被 wrapper 自动 `--resume-campaign` 恢复了
  smoke#3 旧 checkpoint（实验不干净，state 已存证 spike_e1_smoke3_resumed_state.json）。
- 死点仍是 6×6 master_solve iter1——但 M5 第五刀（同条款同参数 master-only 直建、
  **无 jemalloc**）512.9s 绿。头号嫌疑=wrapper 的 `JEMALLOC_CONF dirty/muzzy_decay_ms=-1`
  （「内存只增不减」的 witness 时代延迟优化）在 swap 条款下把 62G 总预算累积吃穿。
- **E1b（进行中）**：同条款同参数、绕 wrapper 去 jemalloc、干净 state。
  活=jemalloc no-decay 实锤 → wrapper 修订（decay 改有限值或加开关）后重跑 E1；
  死=exploratory campaign master 本身内存需求高于 master-only → 深挖装配差异。

### E1b 结果（2026-07-10 21:25）：jemalloc 假说证伪，死因收敛到 master solve 默认参数

E1b（绕 wrapper 无 jemalloc + 干净 state + 42G 帽 + 20G swap + exploratory 6×6）：**exit 137 oom-kill @26.5min**，RSS 峰值 40.2G + swap 顶满 20G（scope 记账 40.2G peak/20G swap peak），死前未写出任何 checkpoint（第一个 master solve 未完成）。RSS 曲线为完美线性爬升（~2.2G/min，16 分钟到帽后溢出全进 swap）。

- **jemalloc no-decay 假说证伪**：E1（有 jemalloc）21.5min 死、E1b（无 jemalloc）26.5min 死，同型。
- **重新归因**：campaign 链 master solve 用产品默认参数（FIXED_SEARCH+probing3+symmetry3）——与 M5 归因判决完全一致（smoke#2/#4 同型死；第四/五刀同代码+原型参数 `automatic/probing1/symmetry1/EXACT_SUBPROBLEM_MAX_MEMORY_MB=28000` 分别 506s/513s 绿）。线性内存增长是该 solve 的搜索状态常态（第五刀也爬到 41.9G+18.1G swap），分野只在出解时机：原型参数 ~8.5min 出解赶在吃穿前，默认参数不出解先吃穿。
- **E1c 设计**：E1 形态（wrapper 42G+20G swap+exploratory --campaign-hours 1 --area-upper-bound 36+干净 state）+ 原型参数 env 注入（四个 env 均在 benders operational allowlist；exploratory 下无 deny-unknown 问题）。预期：首个 6×6 solve ~9min 出解、campaign 继续推进、1h 预算耗尽正常退出。若仍死 → campaign 链还有装配差异（guided profile 候选）继续二分。
- **spike 含义**：E1/E2 的 wall 对照将在原型参数形态下进行——这不损害 spike 效度（GO/NO-GO 看 attach on/off 的相对退化，两轮同参数），但 GO 判定报告须注明「产品默认 solve 参数在 C1 上不可用」是 M5 线待解的独立前置。

### 更正（2026-07-10 21:55）：E1b 归因有误——E1b 已带原型参数，「默认参数死因」被证伪

转录核查发现 E1b 的实际启动命令**已注入原型参数 env**（probing1/symmetry1/automatic/软cap）且带 `taskset -c 4,5`。因此上节「重新归因到产品默认参数」不成立——E1b 带原型参数照样 26.5min 死。E1c（=E1b+jemalloc，因误判参数缺失而设计）无新信息量，预期同死（跑到 23min 时 swap 15.4G 在涨，与 E1b 同轨）。

修正后的干净二分矩阵：

| 实验 | 参数 | CPU | 形态 | 结果 |
|---|---|---|---|---|
| 第五刀 | 原型 | 全核（无 taskset） | 直建单 solve | 绿 512.9s |
| E1b | 原型 | 2 核 taskset | exploratory campaign | 死 26.5min |
| E1c | 原型 | 2 核 taskset | 同上（+jemalloc） | （待死亡确认） |

剩余变量只有两个：**① wrapper taskset -c 4,5（本机 P-core 检测只选出 2 个最高频核，6 workers 挤 2 核）②campaign 装配 vs 直建**。机理估算支持 ①：2 核让 automatic 搜索 ~3 倍慢（出解点 9.6min→~29min），而内存 ~2.3G/min 线性增长在 ~27min 吃穿 62G 预算——E1b 26.5min 死与此吻合（死在出解线之前一步）。**E1d**：原型参数+全核（绕 wrapper 的 taskset）+campaign+同条款——绿=taskset 实锤（wrapper 需加 pin opt-out 或修 P-core 检测），死=campaign 装配差异实锤。

### E1d/E1e 终局（2026-07-10 22:35）：破案——E1 系列死因=--exploratory 模式本身；spike 形态修订为直建 harness

**E1d**（原型参数+全核+campaign）：oom-kill@24.75min，41.4G+20G swap，与 E1b/E1c 同型——taskset 假说证伪。死亡记账暴露关键线索：CPU/wall≈0.98（纯单线程），24 分钟根本不在 CP-SAT solve（多线程）里。

**E1e**（py-spy 抓栈，4.5min 处双 dump 同栈）：

```
_add_port_clearance_constraints (master_model.py:4912)
build (master_model.py:4715)
run_benders_for_ghost_rect (benders_loop.py:8659)
run_outer_search (outer_search.py:2879)
```

**死因闭环**：`_add_port_clearance_constraints` 是 exploratory-only 启发式（docstring 自述"exact 模式跳过"），对每 pose×每 front cell 构造含全格占用项的约束——prod-scale 实例上三重组合爆炸，单线程 ~2.25G/min 线性吃内存直到吃穿 62G。E1 系列四连死与 42G 帽/jemalloc/solve 参数/taskset/C1/campaign 结构全部无关。

**exploratory 模式在 prod-scale 上的三重不可比（决定 spike 弃用该路线）**：
1. master 走 legacy build（`_coordinate_delegate` 构造条件是 `if self.exact_mode:`，master_model.py:2605）——非 C1 生产 master；
2. 实例集是 all_facility_instances（非 266 mandatory）——问题本身更大；
3. port clearance 启发式无开关（build :4715 无条件调用）——prod-scale 下 build 阶段即死。

**spike 形态修订（owner 授权范围内自主拍板，理由如上实锤）**：弃「exploratory campaign 端到端」，改 **certified_exact 直建 harness 对照**（= 代码注释 benders_loop.py:7830 sanctioned 的 "direct (non-certified) invocations and unit tests" 通路；harness 为 docs/research 实验脚本，不改生产代码、不产证明材料）：
- **E1'基线**：certified 直建 C1 master（266 mandatory）+ 第五刀配方 build+solve——**第五刀 512.9s 数据直接复用**；
- **E2'通电**：同 harness，master build 后按 `test_step_8_apply_to_master.py` 的现成形态构造代表性 cut 集（目标 ~10K，F1/F5/F6/F7 已接线族），走 `step_8_apply_to_master` 唯一生产 apply 通路计 attach wall，再 solve 计退化；
- **GO 判据不变**：attach 开销+solve 退化 <50%。

### E1' 正式基线落地（2026-07-10 22:53）

harness 直建（`--cuts 0`，42G 帽+20G swap+第五刀参数）：**OPTIMAL@513.5s**，core build 11.0s + master build 16.0s，branches 4,879,651 / conflicts 486——与第五刀（512.9s / 4,898,023）同分布，harness 本体自证通过。基线三元组（build 27s / attach 0 / solve 513.5s）即 E2' 对照的分母；GO 线（<50% 退化）= E2' 总 wall < ~810s。E2' 待 codex 侦察（step_8 直调材料）回填 harness attach 段后执行。

### E2' 设计定稿（2026-07-10 23:20，codex 侦察六问全答后拍板）

**关键侦察事实**：step_8 裸调只需 Cut+master（无 BState/validator/预算 cap，10K 不被挡）；当前工件自然 cut 空间仅 ~257 条（F1=129 碰边 anchor+F6=128 边界 anchor，F5/F7=0）；CP-SAT 约束不可卸载→对照必须两个全新 master（分进程跑，已满足）；ghost-conditioned cut 挂单 anchor 会被 solver 绕开而低估退化。

**主 workload 拍板 = `static-overlap-f5-10k`**：harness-local F5 direct-lowering——两个不同 mandatory group（同 facility template，如 manufacturing_3x3 8 组）共享同一真实 pose_id 的二元 pattern，occupied cells 完全相同 → NoOverlap2D 必禁 → cut 数学冗余（不改可行集），组合空间 >10K 条内容各不同；`ghost_rect=None` 静态 BState → GHOST_AGNOSTIC → step_8 无条件 attach（全部活跃，规避单 anchor 低估）。计时口径：cut 预制+integrity/validator/Step6 预验全在计时区外；attach 计时=纯 step_8 循环；solve 同基线口径。附加对照（可选）`natural-duplicate`（257 条真自然 F1/F6 重复到 10K）测 production-like 每条成本。

**F5 治理冲突裁决（codex 风险 #14）**：本规格前段三硬门拍板的「F5 shadow、不 mutate master」是**生产通电**的治理豁免条款，继续有效；E2' 的 F5 direct-lowering 仅是 **spike workload 构造手段**（借 F5 的 lowering 形态制造 10K 条各不相同的数学冗余约束测工程开销），不预演生产 F5 治理形态、不宣称模拟生产 convergence（Step 7 在真实 incumbent 上对这些 pattern 恒假）。GO 报告须复述本裁决。

**harness 落点**：`docs/research/p1_3a_attach_power_on_spike_20260710/e2_harness.py`（调研工件，同 batch0_prod_runner 定位）；实现=codex（续侦察 thread）；正式跑=主会话（单发铁律+42G/20G 条款+第五刀参数）。断言三件套（exact_mode/coordinate delegate/c1 representation）+ `coordinate_framework_cut_count` 增量核对 + 不设 `EXACT_CUT_FRAMEWORK_ATTACH`/`EXACT_F7_GENERATOR_ENABLED`/`EXACT_USE_POSE_BOOL_MASTER`/`EXACT_MASTER_HINT_PERSISTENCE`。

**E2' 实现期拍板（23:35，codex 发现规格硬冲突）**：GHOST_AGNOSTIC F5 在 lifecycle step_8 走无条件 attach 分支（lifecycle.py:1393-1402 传空 condition_lits），但 coordinate delegate 对 F5 空条件直接拒（exact_coordinate_master.py:8050-8051 `if not condition_lits: return False`）→ step_8 fail-closed RuntimeError——**agnostic F5 attach 路径在生产代码上从未打通**。裁决=harness-only master shim（空条件→共享恒真 literal 后调真实 delegate；约束形态多一层 `OnlyEnforceIf(恒真)`，presolve 预期消除，报告须注明形态差异并对照 proto 约束数）；拒绝 ghost-bound（单 anchor 被 solver 绕开=风险 #10）与改生产 delegate（sealed 文件 reseal 长链，为 spike 不值）。**TRIAGE 记录**：lifecycle 与 delegate 间的 agnostic-F5 语义缝（fail-closed 安全、无 soundness 问题，但 attach 通电线落地 F5 时须二选一：delegate 支持空条件或 lifecycle 禁止 agnostic F5 进 step_8），与 cut 修复批 replay 诊断残留同级，留通电线处理。

### 判决(2026-07-10 深夜):GO——证据与效度边界见 02_spike_evidence.md

E2' 10K 对照:solve OPTIMAL@534.8s(基线 513.5s,+4.1%),attach 16.55s,总 wall +6.9%(GO 线 <50%);proto 约束 ×4.15 而 solve 几乎无感。四条效度注脚+agnostic-F5 TRIAGE 随判决移交通电线。
