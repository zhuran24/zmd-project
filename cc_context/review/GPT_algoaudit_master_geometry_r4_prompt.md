# 终末地 IndustrialPlanner 精确求解器 — 几何 master round 4 (F-GM-Q3-01-R3-A 修复攻击面 + optional 基数有效不等式族双向保真角度)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_278e4d67.zip`, sha256 `278e4d67f97a88cab7bba697ec96df2f04d43ce1475bc65aef4a22519d1885a0`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: **master 放置** → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = `src/models/exact_coordinate_master.py` + `src/models/master_model.py` 几何/基数侧。

## 本面历史与本轮定位

轮次史: r1 (B-01 footprint bbox 派生 → 已修) + 再审 (2 finding 已修) + 确认 1 轮零; 双向保真轮抓 **F-GM-Q3-01** (protocol storage 下界忽略 fixed 槽 → `0 >= 1` false-INFEASIBLE, 已修); **r3 抓对偶残缝 F-GM-Q3-01-R3-A 已修**: r2 修复只盖 `fixed >= lower`; `0 < fixed < lower` 时 residual protocol 池仍被「存在 fixed required count 就整体跳过」砍掉 (bucket 准备点 + slot 创建点两处) → shortfall 无 literal 可补 = 合法 fixed+residual 混合配置 false-INFEASIBLE (probe: demand=4/slots=3→lower=2, fixed=1 → 未修 INFEASIBLE/修后 OPTIMAL); 同源第三处 master_model powered residual 统计同口径排除。修 (lock F-GM-Q3-01 条款扩写 R3-A) = `_needs_residual_optional_slots_after_fixed_required()` 单一谓词供 bucket/slot 两处共用 (protocol: `lower > fixed` 才留 residual 池; 其它模板维持 fixed 全代表语义) + residual upper bound 扣 fixed 防双花 + powered residual 统计同步口径。与 r2 同属 latent+API 路径 (默认 certified `build_exact_core` 不传 counts 恒空 → 行为全等)。r3 还核了对称破除保真 (匿名槽标签裁剪论证) 与 ghost 锚点域完备性 (半开域 probe 全等)。**本轮 r4 = R3-A 修复确认 + 刻意换角度**。

注意: 包内带着其它面同期修复 (lock 末 F-BL-R4 / F-CUT-R3 / F-RT-R3-01 系列), 各有线别重报。

## 审查重点 (按优先级)

### Q1 F-GM-Q3-01-R3-A 修复确认 (攻击面)

① 单一谓词 `_needs_residual_optional_slots_after_fixed_required()` 的全部调用点: bucket 准备与 slot 创建之外, 还有没有第三处按旧逻辑 (`fixed>0 即跳过`) 判 residual 池存在性的 (全文件 + master_model 跨文件)? ② upper bound 扣减 `max(0, upper - fixed)` 的边界: `upper < fixed` 时返回 0 — 这个输入形态合法吗 (fixed 计数来源 vs certified upper bound 来源是否可能不一致), 0 池 + shortfall>0 时编码回到 `0 >= shortfall` — 此时是真 INFEASIBLE 还是输入不一致该 fail-closed 报错? ③ powered residual 统计与 delegate 池的口径在三种区间 (`fixed=0` / `0<fixed<lower` / `fixed>=lower`) 逐一相等吗 (旁路分裂是 r3 的同源第三处, 确认修复后两边用的判定输入完全一致)? ④ `protocol_storage_box` 特判 vs 其它 required optional 模板「fixed 全代表」语义: 有没有第二个模板未来会有 lower bound 而落入同型缝 (枚举当前全部 required optional 模板与其 bound 来源)?

### Q2 optional 基数有效不等式族双向保真 (新角度)

`_add_exact_optional_cardinality_bounds()` 与其输入链的全族审查: ① **upper bound 方向** (false-INFEASIBLE 风险): `_certified_optional_slot_upper_bounds()` 的每个模板上界从哪推导, 是「规则蕴含的有效不等式」还是「启发式估计」— 给出每模板上界的推导依据与规则溯源; 有没有合法解需要的数量超过编码上界的构造? ② **lower bound 方向** (false-INFEASIBLE 风险): protocol 下界 `ceil(generic inputs / wireless slots)` 之外还有没有别的 lower bound 登记点; wireless slots 参数注入链 (F-BIND-R3-04 修复后从 master core 快照流入) 与本面消费的一致性。③ **power pole family bounds**: pole family 计数上界/瀑布激活约束的双向 — 上界会不会拒掉需要更多杆的合法覆盖, 瀑布激活会不会切掉「只有高编号 family 可行」的配置 (r3 论证了匿名槽交换, family 间是否同样可交换)? ④ slot pool 0 上界时整族约束的退化行为 (空池 + 各 bound 组合) 矩阵。

### Q3 抽查维持 + 挂账复核

① r3 非 soundness 观察复核: 部分 order-key/active-prefix canonicalization 不受 `enable_symmetry_breaking` 控制 — 独立判读这是否纯配置语义问题 (flag 关掉后仍裁匿名标签 = 解空间保真不受影响?), 若有任何裁真解的组合给 probe。② B-01 footprint bbox / mode-channel / r2+r3 回归在场抽查。③ ghost 半开锚点域抽 1 处。

## 明确不要报的

- r1/r2/r3 已修 finding 本体复述 (但其修复的**新**缝算)。
- binding/routing/preprocess/campaign/cuts 各面 (lock 末同期修复系列各有线); pose-bool delegate 的 cell-pattern cut 归 cuts 面 (F-CUT-R3 刚修过) 不在本面。
- 设计决策 (canonical/266/52-Port)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 `adcc2a6e…`, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B 禁区; exploratory 不审。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2964 passed, 0 failed; 包内为 2963 基线 — face 1 r5 的 +1 回归不在包内, 与本面无关)**; 跑不完跑专项 (test_master / test_exact_coordinate_protocol_bounds) + 如实声明 (`-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); false-INFEASIBLE 类给被误拒的合法配置实例; 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q2 模板×bound 方向×推导依据对照表与 Q1 三区间口径核对结果。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = R3-A 修复确认 + optional 基数不等式族双向保真 + 挂账复核; 其余面不审。
