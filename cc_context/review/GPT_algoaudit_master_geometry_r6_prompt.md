# 终末地 IndustrialPlanner 精确求解器 — 几何 master 面 round 6 (饱和确认轮·R5-A 修复确认 + 解回读保真 + master 侧 cut apply 通道)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_3f4ceebb.zip`, sha256 `3f4ceebb5606d2d2b054b5af82899202fc1dcdae8cee9c97626bbaf57b8e58b9`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面定义与历史: 几何 master (`src/models/exact_coordinate_master.py` + `src/models/master_model.py`), 收敛轨迹 …→1 (r4)→1 (r5), 本轮目标连零起步

本面近 3 轮 (报告在包内 `cc_context/review/archive/`): r3 = F-GM-Q3-01-R3-A (shortfall residual 池); r4 = F-GM-Q3-01-R4-A (fixed pole 不承担杆语义 → 接入 family/witness 通道); **r5 = F-GM-Q3-01-R5-A (R4-A 自身退化边界: family 映射为空时 [skip_power_coverage 或无 powered demand] `_attach_required_power_pole_family_channels()` 拿到空 tuple 表 → 对 fixed pole `Add(0==1)` 判死合法纯几何配置; 修 = 空映射跳过 attach [fixed pole 保留几何 slot 经 `_all_power_pole_slots()` 被存在通道读取], 非空映射空表保留 fail-closed)**。r5 已核 `_all_power_pole_slots` 读取点全扫 + slot域×pool 对接 8 行 + specs 文本对照 9 行 (ghost「空」口径/max_lex 分工)。**本轮 r6 = R5-A 修复确认 + 两个未审角度**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-BIND / F-BL-R3..R6 / F-RT-R2..R5 / F-CUT 系列 / F-PRE-R8..R10 条款), 这些面各有自己的线, 别在本轮重报。

## 审查重点 (按优先级)

### Q1 F-GM-Q3-01-R5-A 修复确认 (攻击面)
① 「family 映射为空」的判据 `not self._power_pole_family_name_by_int` — 这个映射为空的全部成因路径 (skip_power_coverage / powered_template_demands 空 / 其它?) 与「确实不需要 family 语义」是否严格等价 — 有没有「映射意外为空但其实有 powered demand」的构造 (那时跳过 attach = fixed pole 逃出 family 计数 = R4-A 复发)? ② 修复后空映射路径上 fixed pole 的几何约束 (no-overlap/在界/ghost 互斥) 是否完整保留; ③ 非空映射但 tuple 表空的 fail-closed 路径还有效吗 (回归在吗)?

### Q2 解回读保真 (新角度): master 解 → solution dict → 下游消费全链
master CP-SAT 解出来后经 `extract_solution()` (或同等物) 转成 placement dict 给 binding/routing/campaign 消费。请审这条回读链: ① `(x,y,mode) → pose_idx → facility_pools[tpl][pose_idx]` 的反查在所有 slot 类别 (mandatory/fixed required/residual active) 上是否无歧义 (同 (x,y,mode) 对应多个 pose_idx 的可能性? mode token 的 footprint key 是否足够区分)? ② 未激活 residual slot 的回读处理 — 会不会把 inactive slot 的残留坐标值当真实放置读出 (CP-SAT 对未约束变量可赋任意域内值)? ③ ghost 矩形的回读 (selected anchor/尺寸) 与 placement 的一致性; ④ `_last_solution` 缓存的失效时机 — face 1 r6 已核 cut apply 成功会清 `_last_solution`, 请从 master 侧补 — 还有哪些模型变更路径 (新增约束/hint/重 solve) 须清而未清 (stale 解被 extract = 错位消费)? ⑤ bound state extraction (`test_master_extract_bound_state` 所盖的通道) 的语义。

### Q3 master 侧 cut apply 通道 (新角度; 与 face 1 r6 的 benders 侧判读互补, 从 master 实现侧攻)
`exact_coordinate_master` 的 cut 应用函数族 (whole-layout conflict nogood / presence-literal 解析 / condition OnlyEnforceIf): ① conflict member → present literal 的解析: 同一 (instance, pose) 在不同表示 (group_id+pose_idx vs instance_id vs 坐标) 下的解析是否一致, alias 检测 (两 member 解析到同一 literal) 的处理是 fail (正确) 还是去重继续 (nogood 变弱, `<= N-1` 的 N 数错了方向是哪边)? ② condition literal 经 `OnlyEnforceIf` 挂在 cut 上 — OnlyEnforceIf(condition) 语义 = condition 真时 cut 生效; condition 假时 cut 不约束。确认 condition 的极性没反 (反了 = ghost A 的 cut 在 ghost B 下也生效 = over-cut); ③ `sum(present_lits) <= N-1` 的 N 与实际加进 sum 的 literal 数一致吗 (解析跳过某 member 但 N 没减 = cut 变松 [安全]; 反向 = over-cut); ④ cut 应用后的 `_last_solution` 清理与返回值 all-or-nothing 语义复核 (face 1 r6 从 caller 侧核过, 请从实现侧确认无部分应用状态残留)。

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r2-r5 已修 finding 与已审结论 (重复报不算)。
- preprocess/binding/campaign/scheduler/routing/cuts 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- canonicalization 不受 enable_symmetry_breaking 控制 (已判配置语义); `upper<fixed` 真 INFEASIBLE + 诊断建议 (已挂账)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2974 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q2 回读链逐环判读与 Q3 apply 通道极性/计数论证。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = R5-A 修复确认 + 解回读保真 + master 侧 cut apply; 其余面不审。
