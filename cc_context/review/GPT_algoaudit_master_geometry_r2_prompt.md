# 终末地 IndustrialPlanner 精确求解器 — 几何 master 面确认轮 (可行域双向保真角度)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_audit_snapshot_6867b7ce.zip`, sha256 `6867b7ce75b5aa61efe9864572cc1b2781ea68d07bcf7efeca28a3ec8ee3487b`。**只认这个文件名, 文件区其它旧快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: **master 放置** → binding → routing → flow)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面历史与本轮定位

几何 master 面 (`src/models/master_model.py` 几何核心 + `src/models/exact_coordinate_master.py` ghost 矩形) 轮次史:
- 首轮抓 **B-01** (no-overlap 用模板固定尺寸非真 footprint, 竖向 pose 4x6 被当 6x4 → false-CERTIFIED 方向), 修复 = footprint-keyed mode-channelled interval (commit 链内)。
- 再审轮抓 2 finding 已修: footprint bbox 复用到 power coverage 存在性见证时 L 形 footprint 的 bbox 洞被误算覆盖 (false-FEASIBLE, latent — 当前候选全矩形) → 加 powered footprint 矩形性检查 fail-closed 回退精确 coverer 表; guard TIMEOUT 后 stale incumbent 可被 extract (加 `_connectivity_guard_accepted` 标志)。
- 确认轮零 finding (穷举验证矩形性检查全池超集 / coverer 表逐 pose 精确 / guard 状态机无 stale-accept)。
- **当前连零 1, 本轮 = 第 2 个干净轮确认, 刻意换角度**: 前几轮主攻"欠剪" (overlap/coverage 漏判 → false-CERTIFIED); 本轮**双向**审, 重点补"过剪" (master 约束比规则严 → false-INFEASIBLE → max_lex 漏真最大矩形 = objective 级 false-CERTIFIED)。

注意: 包内 `master_model.py` 还带着 binding 面 (另一条线) 刚落的 F-BIND-R2-01 loader 委托修复 — 该修复本体不在本面范围, 但它对 master 构建的涟漪 (canonical 角色校验在 master 构造时机触发) 在 Q3 范围内。

规则真相源: `rules/canonical_rules.json` (facility 尺寸/port_rule/clearance), `data/preprocessed/candidate_placements.json` (pose 池, 含 occupied_cells/port cells), specs/06 (候选枚举) / specs/07 (master 模型)。

## 审查重点 (按优先级)

### Q1 no-overlap 与 footprint 的双向保真 (最重要)
- **过剪方向**: footprint bbox over-approximation — lock 允许"非矩形 footprint 保守用 bbox 但不得 under-approximate"。对非矩形 footprint, bbox 比真实 occupied_cells 大 → 两个 L 形可以咬合的合法布局会被 bbox 判重叠拒绝。当前池里有没有非矩形 footprint (上轮说当前全矩形 — 独立验证这个声明, 给出统计)? 若全矩形, bbox = 精确, 无过剪; 若有非矩形, 这是 active false-INFEASIBLE 还是 latent? interval/delta encoding 的边界 (x+w vs x+w-1) 有没有 off-by-one 导致相邻不重叠 pose 被判重叠?
- **欠剪方向**: mode-channelled footprint 对每个 (pose_idx, orientation, port_mode) 通道的选择逻辑 — 通道选错 (如 port_mode 不影响 footprint 的假设) 会不会让真实更大的 footprint 用了更小的 bbox?

### Q2 ghost 矩形与 admissibility 的双向保真
`exact_coordinate_master.py`: ghost 矩形 (目标空矩形) 的 no-overlap 编码 — ghost 与设施的互斥是否恰好 (ghost 边界与设施边界相邻但不重叠的布局必须合法)? `min_side >= 6` admissibility 的编码位置与方向 (它是 admissibility 不是 tie-break, lock 明文)? ghost 全包围合法 (无 exterior-path 要求, lock 明文) 在编码里是否真的没有被偷偷加上连通性约束? (w,h)/(h,w) 双向 orientation 的覆盖 (V75 已封, 抽查编码端)?

### Q3 master 硬约束清单的规则可追溯性
穷举 master 的每一族硬约束 (no-overlap / bounds / power coverage / clearance / boundary 资源池容量 / certified optional lower bounds / 其它), 对每族回答: 它对应 canonical/specs 哪条规则? 有没有比规则更严的"工程近似" (近似必须是保守方向且有 lock 依据)? 特别审 `infer_certified_optional_lower_bounds` (F-BIND-R2-01 修复后它吃 fail-closed loader 的输出) 的推导数学: 下界公式对 wireless final 槽需求的换算 (需求 2 → storage box 下界 1) 是否恰好, 会不会在合法配置下推出过强下界?

### Q4 前轮 "无 finding" 复核结论抽查
前轮判了: 矩形性检查覆盖全池超集 / 缺 occupied_cells 在 domain 构建期 fail-closed / coverer 表逐 pose 精确无 bbox 洞 / guard 标志状态机无 stale-accept / delta-encoding 计数 6。抽查其中论证最薄的 1-2 项, 独立验证或推翻。

## 明确不要报的

- B-01/矩形性/guard 标志已修 finding 本体 (重复报不算; 但其修复的**新缝**算)。
- 设计决策 (canonical/266/52-Port/omni_wireless, owner 已定); B-02 已 refuted (pose-bool master 非公开路径, env guard 拦截)。
- binding 面 F-BIND 系列本体 (另一条线); preprocess/campaign/scheduler/routing/cuts 各面。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 `adcc2a6e…`, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2941 passed, 0 failed)**; 跑不完就跑专项 (test_master / test_exact_contract / test_v84_terminal_layout_max_empty_rect) + 如实声明 (`-p no:randomly`)。
- 注意: 包内 master_model.py 带着 binding 面 (另一条线) 的 F-BIND-R2/R3 修复 (loader 委托 + strict JSON + wireless 槽数参数化) — 修复本体不在本面范围, 但它们对 master 几何/约束构建的涟漪在 Q3 范围内。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 过剪类 finding 给出被误拒的具体合法布局实例; 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **冻结工件条款**: 若修复牵涉登记 hash 的冻结工件, 交付必须含再生步骤 + 期望 sha256/字节数 + 登记位置清单。canonical 内容扩展是 owner gate, 只能报不能改。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q3 实际穷举的约束族×规则对照矩阵 + Q1 的 footprint 矩形性统计。

## 范围边界

- 重点 = no-overlap/ghost/约束族双向保真; 其余面不审。
