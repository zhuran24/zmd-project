# 终末地 IndustrialPlanner 精确求解器 — Benders/LBBD 主循环面 round 6 (饱和确认轮·R5-PS 修复确认 + cut/缓存生命周期 + 时间预算终验)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_70457b5e.zip`, sha256 `70457b5e6cd759fd0fd75873b12b61f444ad3e569bb26216cea7aa383b22b15a`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。
注意: 包基点之后仓库又落了 routing 面 F-RT-R5-01 (外置 domain 与 free_cells 求交) 与 preprocess 面 F-PRE-R10 系列修复, 都不在 benders_loop 主体; 本面主体文件与包一致。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面定义与历史: Benders/LBBD 主循环 (`src/search/benders_loop.py` 为核), r3-r5 收敛轨迹 2→1→0, 本轮目标第 2 个干净轮

本面近 3 轮 (报告在包内 `cc_context/review/` 与 `archive/`): r3 = F-BL-R3-01 (预算耗尽误当穷尽证明铸 nogood) + F-BL-R3-02 (routing 非三态 status 落 INFEASIBLE 分支); r4 = F-BL-R4-01 (binding 状态契约同型缝五消费点, `_record_unexpected_binding_status()` 统一 fail-closed); **r5 = 零 soundness finding (五消费点核对表 + 跨 candidate 共享态 13 行清单 + summary 时序) + 1 LOW 已修 — F-BL-R5-PS-01 (env 门控 power placement forensic 分支非契约 status 直接 UNKNOWN 返回不写对齐 summary = status×summary 错配, 完整性非 soundness; 修 = 返回前写 fail-closed summary [stage="power_placement_subproblem" / power_placement_status / master_follow_up="fail_closed_unknown"])**。**本轮 r6 = 确认轮, R5-PS 修复确认 + 刻意换两个未审角度**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-BIND 系列 / F-GM-Q3 系列 / F-RT-R2..R4 / F-CUT-R2 + CUT-R3-H1/CUT-R4-H1 / F-PRE-R8/R9 条款), 这些面各有自己的线, 别在本轮重报。

## 审查重点 (按优先级)

### Q1 F-BL-R5-PS-01 修复确认 (轻量攻击面)
① 修复写的 fail-closed summary 字段集与其它 UNKNOWN 路径的 summary 形状是否对齐 (下游 forensic/telemetry 读取处不会因字段缺失 KeyError 或误读)? ② 该 env 门控分支 (`EXACT_POWER_PLACEMENT_SUBPROBLEM`, 公开 certified 被 blocker 拦) 的其余 status 分支 (FEASIBLE/INFEASIBLE/TIMEOUT) 的 summary 写入是否也无错配残留? ③ 修复是否引入了对主链 (env-off) 行为的任何改变 (应零变化)?

### Q2 Benders iteration 间 cut/缓存生命周期与单调性 (新角度)
LBBD 的正确性依赖「加进 master 的每个 cut 永远有效」。请独立审: ① **master 上累积的每类 cut** (binding/routing 穷尽 whole-layout nogood / front_blocked ladder 各形态 / lazy connectivity cut / 条件化 power witness nogood) 的有效性证明是否依赖「加 cut 时刻」的瞬时状态 (binding model 内容/routing 域/iteration 计数) — 若依赖, 跨 iteration 与跨 candidate 复用时该前提还成立吗 (cut 污染 = soundness 缝)? ② cut 的 condition literals (ghost anchor 等) 解析失败时是 fail-closed 不加还是降级为无条件 cut (后者 = over-cut)? ③ 各类**缓存** (binding cache / subproblem reuse / shrink counters / 域分析缓存) 与 proof 的关系: 缓存命中返回的结果有没有可能来自「不同前提下的旧解」被当新前提的证明消费? 逐个判读 proof-bearing vs telemetry-only。④ iteration 推进的终止论证: cut 必须严格削减 master 解空间, 有没有「加了 cut 但 master 可返回同一解」的循环路径 (活锁方向, 完整性非 soundness, 但若靠 iteration cap 兜底则 cap 命中必须 UNKNOWN — 与 F-BL-R3-01 一致)?

### Q3 时间预算传递与耗尽路径终验 (新角度)
certified 主链上每个 stage (master solve / binding solve+重解 / routing precheck / routing solve / guard / 各 separator) 的时间预算: ① 预算从 campaign 层到各 stage 的传递链 — 有没有 stage 用了硬编码默认而非传入预算 (导致超预算运行或过早截断)? ② **每一条**预算耗尽/TIMEOUT 路径的终态: 逐条列出并判读是否都收敛到 UNKNOWN/TIMEOUT 而非 INFEASIBLE/CERTIFIED (r4 核过主干, 本轮请穷举包括 separator/guard/precheck 在内的全部 timeout 出口); ③ 时间测量本身: 用的是单调时钟吗? 预算检查点之间最长可能的「未检查窗口」是否有界 (一个 stage 内部死循环无预算检查 = 挂死方向)?

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r3-r5 已修 finding 与已审结论 (重复报不算)。
- preprocess/binding/master 几何/campaign/scheduler/routing/cuts 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- facility_pools pose dict 浅拷贝共享 (r5 已挂账保守备注, 当前无 mutation 路径)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2972 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q2 cut 类型×有效性依据矩阵与 Q3 timeout 出口清单。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = R5-PS 修复确认 + cut/缓存生命周期 + 时间预算终验; 其余面不审。
