# 终末地 IndustrialPlanner 精确求解器 — campaign/resume 状态机面 round 4 (真 Pro 重审·持久化与 resume soundness)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_f4418b04.zip`, sha256 `f4418b045b257e186c0d06ad6045908a33118d597b8f65666fb39691378965d1`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照 (HEAD 2e1da65)。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **campaign 持久化 / resume 状态机** (`src/search/exact_campaign.py` 为核, 配 `src/search/certified_frontier.py` 终局证据 + `src/search/outer_search.py` 的 frontier 重建/终局提交)。**并行 scheduler 合并是 face 8 单独审, 本轮不审。**

## 本面定义与历史 + 本轮性质 (关键, 必读)

本面 = **状态机 soundness**, 不重新证明 LBBD 子问题正确性 (那是 master/routing/cuts/preprocess/binding 各面的事)。它把单个候选的 CERTIFIED/INFEASIBLE 判定当作「在同一冻结 artifact hash 下已正确」来信任, 只校验: ① 持久化落盘原子性 + 崩溃时序 (写 checkpoint/state 中途崩溃的恢复); ② resume 一致性 (候选不重复消费 / 不丢已证候选 / 陈旧 witness 不穿越状态改写); ③ 终局证据 (full-frontier potential_domain 空 + frontier 空) 不被错误升格成更强主张。历史 (此前与 face 8 同包审, **finding 全部 thinking 模型所抓**):
- r1 = F78-F-01 (HIGH, false-CERTIFIED: 陈旧 candidate solution 穿越状态改写存活 — started 拷入 RUNNING + CERTIFIED(None) 继承旧 witness + 弱状态带 solution 不被校验拒);
- r2 = 零 finding (F-01 逐处 file:line 复核 + 全 writer 清单穷举);
- r3 = 零 finding (崩溃时序/原子性: 文件×损坏 13 行矩阵 + 五时刻崩溃推演 + 多进程独占 + 证据隔离, 连零 2 达饱和下沿)。

**本轮 r4 = 真 Pro 重审。关键背景, 决定本轮姿态:**
**此前本面全部轮次 (r1-r3) 都是较弱的 GPT thinking 模型审的; 本轮起切到 GPT Pro 扩展模式。** 同期真 Pro 一切到其它面就抓出 thinking 漏了多轮的真 finding: Benders (F-BL-R7-01)、cuts (CUT-R12-H1 / CUT-R13-H1, thinking 审 11+ 轮没发现)、preprocess (F-PRE-R15-01 / R16-01 / R16-02)、几何 master (F-GM-R11-PB-REQ-POLE-01 / STALE-01)。**所以本面绝不能因为「thinking 连零 2 达饱和」就默认干净 —— 请当作从未深审重走。前轮 clean 不构成任何先验。**

注意: 包内带其它面同期修复, 各面有自己的线, **别在本轮重报**。`candidate_placements.json` 缺失时 `load_or_create` 直接 FileNotFoundError fail-closed (本 checkout 现状), 非本面 soundness 缝。

## 审查重点 (状态机 soundness, 6 块, 行号基于本包 exact_campaign.py / certified_frontier.py / outer_search.py)

### Q1 [false-INFEASIBLE 漏真矩形] 终局只回放最优解, 非最优 CERTIFIED/INFEASIBLE 判定被信任不回放
`terminal_certified_final_result_violation` 内候选扫描 (`exact_campaign.py:1694-1704`) 只确认无其它 CERTIFIED 记录 objective 高于 final; `_validate_terminal_solution_against_project:797-1050` 只几何回放 `final_result.placement_solution` 这一个解。所有 INFEASIBLE 判定 + 所有非最优 CERTIFIED 判定 (它们 derive-prune 掉更小候选, `outer_search.py:663-668`) 在终局时**从不被几何回放**, 完全信任「当初同 artifact hash 下算对了」。请判: 这是合理 trust boundary (冻结 artifact + 子问题 exact) 还是漏真矩形的缝 —— 若某个被信任的 INFEASIBLE 实际 false-INFEASIBLE, 它 prune 掉的更大候选永不重证, 终局 best 可能漏真正更大空矩形。无 file:line 级的「每个记录可重放证书」机制。

### Q2 [false-CERTIFIED 时窗] CERTIFIED→CERTIFIED 重判允许且 solution 无条件覆盖
`mark_candidate_result (:2065-2073)` 只在 existing!=incoming 时 raise; CERTIFIED→CERTIFIED 不触发冲突, `record['solution']=dict(solution)` (`:2136`) 无条件覆盖旧 witness。请构造: 若已 commit 的 terminal final_result 绑定旧 solution, 而该候选被再次 CERTIFIED (不同 solution) → in-memory final_result.placement_solution 与 record.solution 失配。下次 validation 会被 `terminal_certified_final_result_solution_mismatch (:1690)` 抓住? 还是存在「重判后未重新 commit/validate 即 save+export」的时窗? 注意正常 frontier-skip (`outer_search.py:660`) 跳过 CERTIFIED 候选阻止重派, 需确认是否真的没有任何重派路径 (resume 后 records 与 live domain 不一致时)。

### Q3 [false-CERTIFIED 完备性] projection 剪枝须与活跃 frontier 严格等价
终局完备性唯一硬判据 = `compute_terminal_frontier_projection` 产出 `potential_domain==[]` 且 `frontier==[]` (`certified_frontier.py:417-420`)。该 projection 的 skip/derive-prune (`:175-246`) 必须逐行等价于 `outer_search.py:631-693` 的活跃 frontier 构造。请**逐字节对照两份实现找任何不对称** (尤其 UNKNOWN/UNPROVEN/RUNNING 是否两侧都不计入 explicit_* / 都留 potential_domain; best objective 剪枝 projection 用 `candidate_objective<=` 活跃用 `_is_objectively_worse_or_equal`)。任何不对称 → evidence 通过校验但活跃搜索其实漏候选 = false-CERTIFIED 完备性。

### Q4 [false-CERTIFIED] resume 不重放非终局 CERTIFIED 记录几何有效性即用于剪枝
`_validate_candidate_record:1394-1469` 对 CERTIFIED 记录只校验 solution 是 Mapping (`:1434`), 不做几何/witness 回放。resume 后这些被信任的 CERTIFIED 立即进 explicit_certified 并 derive-prune 掉所有 ≤ 它的候选 (`outer_search.py:663`)。请判: schema 合法但几何错误的 CERTIFIED 记录 (人改 checkpoint 或旧 bug 产生) 能否 resume 后静默剪掉真候选? artifact hash 绑定 (`:1503`) 只防 artifact 改动, 不防 checkpoint 内 record 本身被构造/篡改 (r3 挂账「同 hash 旧坏强记录无法自证 provenance 属固有限制」) —— 确认这是否仍是 false-CERTIFIED 实际可达路径, 还是被 best 解终局回放兜住。

### Q5 [崩溃原子性] 双 coordinator 无 lockfile + wave 内多次 best-effort save
r3 把「双 coordinator last-writer-wins」判运维风险非 soundness (论据: atomic write + resume 全校验 + 最多回退进度)。请**独立复核此判定能否被推翻**: 两 coordinator 交错 save 时, A 写 terminal CERTIFIED (final_result+evidence 自洽), B 随后用候选记录被并发改写过的旧内存 state 覆盖 → B 的 save 是否产生「final_status=CERTIFIED 但某参与终局的 candidate record 已非 CERTIFIED」的自相矛盾落盘? 若能, resume 时 `terminal_frontier_candidate_status_digest`/best_candidate 校验是否必然拒之? 确认 commit 顺序 (`outer_search.py:860-879` 先 set 后 validate 后 save, validate 失败 raise 阻止 save) 是否封死。原子写本身: `atomic_write_json:1304-1324` (temp+fsync+os.replace+目录 fsync)。

### Q6 [resume 一致性] time_budget 续跑清 stop 后 final_result/evidence 一致性
`load_or_create:1848-1855` resume 时若 `last_stop_reason==campaign_time_budget_exhausted` 则清 stop + final_status=None 续跑。请确认此清除不与残留 final_result/terminal_frontier_evidence 产生不一致 (`_validate_resume_state` 应已要求 `final_result!=None ⟹ final_status==CERTIFIED`, `:1517`, 故 time_budget 状态本不该带 final_result) —— 核对「final_result 残留 + time_budget stop」落盘形态在 resume 时是**先**被 `_validate_resume_state` 的 final_status_mismatch 拒绝, **还是先**被 budget-clear 改写, 顺序是否留缝。

## 明确不要报的

- 已修条款 (重复报不算): **F78-F-01** (lock:92, 候选 solution 卫生 + 强状态单调); Accepted invariants (lock:87/88/91, best certified 跨持久化单调 + final_solution/manifest 同源 + coordinator-only writer 不相交波次); **F-BIND-R5-01** (lock:103, worker artifact-hash 封印)。r2/r3 已审结论 (同 hash 旧坏强记录无法自证 provenance 属固有限制, 别当新 finding)。
- **跨面边界 (别误判为本面缝)**: ① **F78-F-02 worker 身份绑定 + 并行波次合并是 face 8 (parallel scheduler) 单独审, 本轮不审**; 本面只验状态机/持久化/resume/终局证据, 不验 scheduler 的 worker 结果合并逻辑。② worker 进程内 Benders/cuts/binding/几何 正确性属各自面, 本面只假设 worker 返回 status 语义与 sequential 同源。③ Q1/Q4 的「非最优判定不回放」本质把可信度委托给 routing/binding/cuts/几何 master 面: 若那些面有 false-INFEASIBLE, 本面状态机会忠实持久化并据此 derive-prune, 终局完备性随之失真 —— 这是跨面信任, 别当本面缝。
- 设计决策 (canonical / 266 口径 / `min_side>=6` admissibility, owner 已定); master / routing / cuts / preprocess / benders / binding / scheduler 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 行为/性能不审; persisted `exact_safe_cuts` 是 telemetry 非 proof。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **≈3044 passed, 0 failed** (HEAD 2e1da65)。跑不完就跑 campaign 专项 (`test_exact_campaign*` / `test_v62*` / `test_v97*` / `test_v98*` 等) + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass (8 obligations)。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。
- 契约: `PROJECT_LOCK.md:85-96` (Accepted Invariants + F78-F-01/F-02); `specs/10_benders_decomposition_and_cut_design.md` (LBBD 主从结构, candidate 判定语义来源)。终局证据契约测试 `test_v62_candidate_frontier_contract.py` / `test_v97_canonical_campaign_state_authority.py` / `test_v98_b5a_symlink_campaign_path_authority.py`。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 附三段判读: 持久化原子性 + 崩溃时序 (Q5) / resume 一致性 (Q2/Q4/Q6) / 终局证据完备性 (Q1/Q3) 的真 Pro 复核。
- 真 Pro 首轮重审, 前轮 thinking 连零不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = campaign 持久化 / resume 状态机 / 终局证据 soundness 的真 Pro 复核; **parallel scheduler 合并 (face 8) 与其余面不审**。
