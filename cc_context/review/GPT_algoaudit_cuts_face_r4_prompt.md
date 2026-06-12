# 终末地 IndustrialPlanner 精确求解器 — cuts 机制面 round 4 (CUT-R3-H1 修复攻击面 + lazy-demand/count cut 族本体精确性角度)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_278e4d67.zip`, sha256 `278e4d67f97a88cab7bba697ec96df2f04d43ce1475bc65aef4a22519d1885a0`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。包内与本面相关的主体文件 (pose_bool_exact_master / binding_subproblem / cuts) 与最新 HEAD 一致; benders_loop/routing 有与本面无关的同期后续修复不在包内, 别审它们的新鲜度。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面历史与本轮定位

cuts 面轮次史: r1 (C-3/C-4 latent 挂账); r2 抓 CUT-R2-H1 已修 (cell-pattern cut 把可选 binding 端口当必然激活 + cache double-anchor); **r3 判 R2 修复 sound 但抓同族残缝 CUT-R3-H1 已修**: `_profile_port_demands()` 把 generic 槽当逐口强制需求 — generic output 物理槽的 binding domain 含 `__unused__` (required 只约束真实赋值数), 2 物理口+1 required 时被挡的第一口可留 unused 走第二口 → cell cut 误剪 (probe 实证); generic input 槽是虚拟无线容量 (无物理 front) 同向 overcount。修 (lock F-CUT-R2-01 条款扩写 CUT-R3-H1 + specs/10 §10.8) = input 侧只计 concrete routing-visible demand; generic output 仅在「required 总数 == mandatory 容量总数」全局饱和证明成立时计入 visible (饱和把 `__unused__` 压成 0 = 必然激活); **容量统计 fail-closed** = `_mandatory_generic_output_capacity_total()` 两条路径 (mandatory_groups / fallback operation_by_group) 对「组实例数不可知」一律 return None (skip/假定-1 会少算容量伪造饱和 = 与 finding 同族 over-cut), None ⇒ 不饱和 ⇒ 不登记。r3 还核了 nogood literal 集边界与 condition_lits 全登记点。**本轮 r4 = CUT-R3-H1 修复确认 + 刻意换角度**。

注意: 公开 certified 默认路径上 pose-bool/cell-pattern hook 仍被 `pose_bool_master_not_certified` env blocker 拦; 本面发现多为 env-gated hardening, 但「未来 promote 时升级为 soundness」的前提缺陷照报。包内带着其它面同期修复 (lock 末 F-BL-R4 / F-GM-R3A / F-RT-R3/R4 系列), 各有线别重报。

## 审查重点 (按优先级)

### Q1 CUT-R3-H1 修复确认 (攻击面)

① **饱和证明的前提本身**: `_required_generic_output_slot_total()` 是跨 commodity 求和; binding 侧 required generic outputs 的精确计数约束 (binding_subproblem) 是按什么粒度枚举的 (per-commodity? per-slot 组合?) — 「总和 == 总容量」是否真推出「每个物理槽必然非 `__unused__`」(考虑 per-commodity 分配不均/角色约束/routing-free commodity 被 extract_port_specs 丢弃的交互)? 给出从 binding 编码到饱和推论的逐步论证或反例 probe。② **容量统计两路径**: mandatory_groups 主路径 (`count = group.count 或 len(instance_ids)`) 与 fallback 路径 (operation_by_group × instance_ids) 各自的输入来源在真实 delegate 构建链上是谁灌的 — 两路径对同一状态可能给出不同容量吗 (主路径有 groups 时 fallback 不跑, 但 groups 的 count 字段与 instance_ids 长度不一致时取谁)? fail-closed return None 的覆盖有没有漏 (例如 slots>0 但 profile 抛非 Exception 的路径)? ③ **饱和判定 `required == capacity` 的严格相等**: required > capacity (全局不可行) 与 required < capacity (不饱和) 都不登记 — 还有没有第三种形态 (如 required 含 routing-free commodity) 让相等成立但实际可 `__unused__`? ④ 修复对 `_routing_visible_profile_demands` 其它消费者的传播: 全部消费点清单 + 各自方向判读 (减小 visible 对该消费者是弱化还是错切)。

### Q2 lazy-demand/count cut 族本体精确性 (新角度)

CUT-R2/R3 把混合侧与不饱和侧「留给更弱但 exact 的 lazy-demand/count cut」— 本轮审这个兜底本体: ① lazy-demand/count cut 的形状与有效性定理 (它对 demand 计数用的是哪个函数 — 若也走 `_profile_port_demands`, R3 修复后的 visible 语义对它是否同样恰好: 饱和 generic output 计入后, lazy cut 要求的 free front 数会不会超过 binding 实际需要的 (over-cut), 不饱和不计入会不会漏掉本可加的 exact cut (只是弱化, 但确认方向)?); ② lazy cut 的触发条件与 fail-closed 路径 (demand 不可知/profile 异常时它怎么退); ③ lazy cut 与 cell-pattern cut 在同一 side 上的组合: 两者同时加会不会联合 over-cut (cell cut 管 per-cell, lazy 管计数 — 交集语义)? ④ deletion-core cut 路径 (env `EXACT_B1_DELETION_CORE_CUT`) 对 generic 槽语义的消费抽查 1-2 处 (r2 审过 exact-safe 矩阵, 本轮只确认 generic-slot 语义修复没把它的前提改坏)。

### Q3 抽查维持

V82 persisted cuts telemetry-only 边界 / F1-F9 框架 step_2/step_8 NotImplementedError 边界 / C-3/C-4 latent 挂账文档在场 — 各抽 1 处。r3 的 nogood literal/condition_lits 结论不用全量重审。

## 明确不要报的

- r1/r2/r3 已修 finding 本体复述 (但其修复的**新**缝算); C-3/C-4 挂账本体 (owner 已知)。
- binding/master/routing/preprocess/campaign/scheduler 各面 (各有线; binding 的 `__unused__`/精确计数语义本体归 binding 面, 本面只审 cuts 对它的**消费前提**)。
- 设计决策 (canonical/266/52-Port); persisted `exact_safe_cuts` 是 telemetry 非 proof (V82, 已三轮确认)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 `adcc2a6e…`, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2966 passed; 包内基线 2963 — 差额是 benders/routing 面后续回归, 与本面无关)**; 跑不完跑专项 (src/tests/cuts / test_wireless_front_consumers_r4 / test_binding) + 如实声明 (`-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); over-cut 类给被误剪的可行 placement+binding 实例; 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 饱和推论论证链与 Q2 lazy 族消费点×方向对照表。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = CUT-R3-H1 修复确认 + lazy-demand/count 族本体 + 抽查维持; 其余面不审。
