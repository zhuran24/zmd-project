# 终末地 IndustrialPlanner 精确求解器 — binding 面 round 8 (真 Pro 重审·端口绑定建模 soundness 全面复核)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_f4418b04.zip`, sha256 `f4418b045b257e186c0d06ad6045908a33118d597b8f65666fb39691378965d1`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照 (HEAD 2e1da65)。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → **binding 端口绑定** → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **binding 子问题 (端口绑定 CP-SAT 模型)** (`src/models/binding_subproblem.py` 为核, 配 `src/models/port_binding.py` 域枚举引擎 / `src/preprocess/operation_profiles.py` 容量→槽 / `src/search/benders_loop.py` 的 binding 注入与 safe-reject ladder)。

## 本面定义与历史 + 本轮性质 (关键, 必读)

本面 = binding 子问题是否**忠实编码规则**: 每个 placed mandatory 实例的输入/输出端口 exact-one commodity 绑定、容量 (rate→slot 取整)、generic 通用槽与 wireless 虚拟槽、`__unused__` 哨兵、binding→routing 接口 (`extract_port_specs`)、binding-local safe-reject ladder。**不管** master 几何 / routing CP-SAT 内部 / flow 诊断本体 —— 只管 binding 选出的 port_specs 是否既不 stricter-than-rule (false-INFEASIBLE 拒合法绑定) 也不 looser-than-rule (false-FEASIBLE 放过非法绑定/容量超限/漏证某实例)。历史 (**前轮 finding 全部 thinking 模型或更早所抓**):
- r1 = F-BIND-R1-01 (generic output 槽缺 `__unused__` 哨兵, 把满额 52=52 数值巧合硬编成结构假设, 需求<槽数合法空置被判 INFEASIBLE; latent) + F-BIND-R1-02 (generic I/O / wireless 槽数 loader fail-open: 缺 section 静默空需求 / int() 吞 bool/float/str / 不校验 canonical 商品角色, 中间品冒充终品);
- r2 = F-BIND-R2-01 (master 侧第二个更宽松 loader, 字符串 '100' 被 int 吞 → optional 下界注入 master 硬约束) + F-BIND-R2-02 (JSON 默认接受重复 key last-write-wins 可清空需求 + NaN/Infinity);
- r3-r5 = F-BIND-R3-01..05 / R4-01 / R5-01 (proof 输入单解析单快照: certified binding 接收 master normalized 快照而非重读磁盘; wireless 槽数从 project-root plan 流入; 单快照封印延伸到 outer search + worker, 不一致 fail-closed);
- r6 = 零 finding (枚举/对称数学 + 全 writer 消费点终验矩阵);
- r7 = 零 finding (规则文本独立对照 11 行 + routing-free 三类判读, 连零 2 达饱和下沿)。

**本轮 r8 = 真 Pro 重审。关键背景, 决定本轮姿态:**
**此前本面全部轮次 (r1-r7) 都是较弱的 GPT thinking 模型审的; 本轮起切到 GPT Pro 扩展模式。** 同期真 Pro 一切到其它面就抓出 thinking 漏了多轮的真 finding: Benders (F-BL-R7-01)、cuts (CUT-R12-H1 / CUT-R13-H1, thinking 审 11+ 轮没发现)、preprocess (F-PRE-R15-01 / R16-01 / R16-02)、几何 master (F-GM-R11-PB-REQ-POLE-01 / STALE-01)。**所以本面绝不能因为「thinking 连零 2 达饱和」就默认干净 —— 请把 binding 当作从未被深度审过的面, 用最独立、最对抗的判断重走一遍端口绑定 soundness。前轮 clean 不构成任何先验。**

注意: 包内带其它面同期落的修复, 各面有自己的线, **别在本轮重报**。

## 审查重点 (端口绑定 soundness, 按优先级; 行号基于本包 binding_subproblem.py / port_binding.py / operation_profiles.py)

### Q1 [最高优先 false-FEASIBLE] 实例覆盖完备性 — 每个 placed 实例是否被恰好一条约束路径证明
`_build_fixed_operation_domains:653-655` 对 operation_type 为空 或 `not supports_exact_pose_level_binding` 的 placed 实例 **continue 静默跳过**, 不进任何 binding 域; `_build_generic_output_domains:720` 只对 `{boundary_io, protocol_core}` 建输出槽; `_build_generic_input_domains:768` 只对 `wireless_sink` 建输入槽。请独立验: 266 mandatory 实例 + 合成 pose_optional 是否**每个都被恰好一条路径覆盖** (fixed-op / generic-output / generic-input), 还是存在某 operation_type **三路全不命中** → 该实例端口完全不被任何约束证明 = 放过非法布局。重点查制造 recipe 实例 (`supports_exact_pose_level_binding` 要求 generic_input_slots==0 且 generic_output_slots==0) 会否落入空隙。

### Q2 [false-INFEASIBLE] 空 binding 域来源 — 是几何不可能还是 rate→slot 取整误判
`_build_fixed_operation_domains:677-689` 空 binding 域 → `empty_binding_domain_instances` → `build():462-463` 直接 `Add(0==1)` 造 INFEASIBLE, 且 `benders_loop:5215-5245` 把 binding INFEASIBLE 铸成 `binding_exhausted=True` whole-layout nogood (certified 拒绝该 layout)。空域来源: `port_binding.py:150-153` `total_slots > ordered_cell_count` 会 raise ValueError (非空域), 或 RAB filter 删空。请验: routing_context=None 纯 binding 路径下空域**唯一来源是否真是几何不可能** (端口数不足), 还是 `_rate_to_slots:48-55 ceil(rate/cap-eps)` 把合法配置算成端口不足 → ValueError 上抛 vs 空域 → false-INFEASIBLE。对照 specs/04 §4.8 各机器端口度数 (封装机 5/6 口留 1 空等) 与 `profile.output_slots/input_slots`。

### Q3 [false-FEASIBLE 容量超限] cell 容量是否被结构排除
`port_binding.py:182-197 _materialize_side_binding` 每 cell 恰映射一个 commodity; `_enumerate_side_binding_patterns:143-179` 只检查 `total_slots <= cell_count`。请验: binding 对单个物理端口 cell 的 belt 吞吐是否做容量约束, 还是默认每 cell=1 belt=belt_capacity_per_tick 由 slot 数 (ceil(rate/cap)) 隐式承载。跨 commodity 共享 cell / 多 commodity 在同 cell 叠加是否被结构排除? 确认无端口容量超限被放过。

### Q4 [false-INFEASIBLE/边界] routing-free 终品输出口排除完备性
`extract_port_specs:1021-1025` (固定 output 侧) + `:1055-1061` (generic output 侧) 排除 `routing_free_sink_commodities` (= required_generic_inputs 中 required>0 的商品, `:369-373`)。specs/05 §5.4.3:109 要求排除覆盖生产端实体输出口 + 该 commodity 任何 generic-output 口。请验: `routing_free_sink_commodities` (从 required_generic_inputs 推) 是否**精确等于** canonical `sink_kind=generic_input` 的纯终品集 —— 若某无线终品因 required==0 被漏出该集合, 其生产者输出口被当 routing terminal 导出 → routing 里无 sink 的孤立 source → 虚假 front_blocked → false-INFEASIBLE; 反向误把非终品塞进该集合 → 真实消费链被吞 → false-FEASIBLE。**请独立从 specs/03/04/05 + canonical 推导预期再对照, 勿从实现学语义** (F-RT-R2-01 教训)。

### Q5 [false-INFEASIBLE] safe-reject ladder 终态
`_binding_has_alternatives:6135-6140` 当 binding_vars / generic_input_vars / generic_output_vars 任一非空即返 True; `add_nogood_cut:1090-1106` 只排当前 selection。请验: 当某实例 binding 已固定 (域大小==1, `:693-695` 无 binding_var) 但其它实例/generic 槽仍有自由度时, `_binding_has_alternatives` 仍 True → 继续枚举。front_blocked (`benders_loop:5406-5410`) 路径下, 若 routing-front 阻塞的是固定实例端口、备选只换无关 generic 槽, 会否无效枚举但最终仍因 CP-SAT INFEASIBLE 正确收口? 核对 ladder 终态 (`:5447-5448 break` + `:5215 INFEASIBLE→whole-layout nogood`) 是否**真在 binding 域穷尽时才铸 master 级 nogood** (对照 lock:134/135)。

### Q6 [false-INFEASIBLE] overload separation env 互锁
`_add_storage_box_overload_nogoods:499-554` env-gated 注入 HARD nogood (可砍合法解), 依赖 caller fallback ladder; `_run_binding_overload_fallback:6060-6101` INFEASIBLE 时 env-off 重解。请验 benders_loop 主路径 (`:5014-5022` 构造未传 overload env) 与 retry 交互: 若 `EXACT_BINDING_USE_OVERLOAD_SEPARATION` 未设, 确认 certified 主链**绝不经过** overload nogood; 若被某 wrapper 误开, 确认 INFEASIBLE 必触发 fallback 重解而非直接铸 binding_exhausted nogood (否则 overload 砍的合法解被当真 INFEASIBLE)。核对 env 解析 `:471-474` 与 retry 触发条件是否真互锁。

### Q7 [false-FEASIBLE/INFEASIBLE] `__unused__` 哨兵 + 精确计数
`_add_generic_output_requirements:809-820` 与 input `:796-807`: required==0 时全 var==0, 否则 sum==required。slot domain = 真实商品 ∪ `__unused__` (`:713,:761`), 每槽 ExactlyOne (`:748,:794`)。请验 R<=S 任意非满额配置: `sum(真实商品 var)==required` 精确成立、剩余槽落 `__unused__`、`__unused__` 不进 port_specs (`:1040,:1059`)。重点核对 required 总和 > 可用槽数 (R>S) 时是否**正确 INFEASIBLE** (不依赖 52=52 巧合), 及 `__unused__` 作为保留名是否在所有需求工件装载处被拒 (`:229-234`)。

## 明确不要报的

- 已修 lock 条款 (重复报不算): **F-BIND-R1-01/R1-02** (lock:98/99)、**F-BIND-R2-01/R2-02** (lock:100/101)、**F-BIND-R3-01..05 / R4-01** (lock:102)、**F-BIND-R5-01** (lock:103); 关联 **F-BL-R3-01** (lock:135, budget exhaustion 非 exhaustion proof) + safe-reject 边界 (lock:134)。r6/r7 已审结论。
- **跨面边界 (别误判为本面缝)**: ① 上游 master/preprocess 保证 pose 端口坐标几何正确 (binding 不二次编码几何, candidate poses 已 materialize 端口坐标 = master/routing 候选职责); ② 下游 routing-free 排除的 routing deletion-core oracle / pose-bool master lazy-demand cut / separator 四处对偶执行属 cuts/flow 面, 本面只验 binding 侧 `extract_port_specs` + RAB `_filter_pose_binding_domain:563-605` 排除, **不验 routing 内部是否同步**; ③ generic I/O 需求工件单快照封印的 outer/worker 部分属 campaign/scheduler 面, 本面只验 binding 接收快照而非重读盘; ④ **RAB-SEP (`EXACT_B1_ROUTING_AWARE_BINDING`) / PCR-CUT / pose-bool master 均 env-gated 默认关, certified 主路径 routing_context=None 不经 RAB filter** —— 审 env-on 行为属 cuts 面 cut soundness, 本面只保 env-off 主路径不破。
- 设计决策 (canonical / 266 口径 / omni_wireless 虚拟槽 / 52-Port 满额不变量 / `min_side>=6` admissibility, owner 已定)。
- master / routing / cuts / preprocess / benders / campaign / scheduler 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 行为/性能不审; persisted `exact_safe_cuts` 是 telemetry 非 proof。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **≈3044 passed, 0 failed** (HEAD 2e1da65)。跑不完就跑 binding 专项 (`test_binding*` / `test_port_binding*` 等) + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass (8 obligations)。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。
- 规则文本: `specs/05_facility_instance_definition.md` §5.4.3 (协议箱无线消费语义 + 生产端对偶排除); `specs/04_recipe_and_demand_expansion.md` §4.5 (52 输入口满额) / §4.8 (DEPRECATED 但含各机器端口度数真值); `specs/03_rule_canonicalization.md` §3.4.1/§3.5.1 (多余端口合法空置规则依据)。商品角色真源 `rules/canonical_rules.json` commodity_metadata (source_kind/sink_kind); wireless 槽数 `rules/preprocess_plan.json` utility_operations.wireless_sink.generic_input_slots=3。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 附三段判读: 实例覆盖完备性 + 空域来源 (Q1-Q2) / 容量 + routing-free 排除 (Q3-Q4) / safe-reject + overload + `__unused__` 精确计数 (Q5-Q7) 的真 Pro 复核, 每条约束带规则依据。
- 真 Pro 首轮重审, 前轮 thinking 连零不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = 端口绑定 soundness (实例覆盖 / 容量 / routing-free 排除 / safe-reject / 精确计数) 的真 Pro 复核; 其余面不审。
