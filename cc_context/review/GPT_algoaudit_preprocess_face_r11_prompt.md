# 终末地 IndustrialPlanner 精确求解器 — preprocess 链面 round 11 (饱和确认轮·R10 修复确认 + demand solver 数学本体 + canonical 投影保真)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_3f4ceebb.zip`, sha256 `3f4ceebb5606d2d2b054b5af82899202fc1dcdae8cee9c97626bbaf57b8e58b9`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面定义与历史: preprocess 链, r1-r10 收敛轨迹, 本轮目标第 2 个干净轮序列重启

preprocess 面历史 10 轮 (报告在包内 `cc_context/review/` 与 `archive/`): r1-r4 wireless routing-free 链; r5/r7 零; r6 = plan overlay+hash 闭包; r8 = strict JSON 四装载点; r9 = 数字上溢 (`parse_float`); **r10 = F-PRE-R10-01 (path loader strict-load 后从不跑 schema 校验, schema-required 字段缺失被代码默认值吞 = fail-open; 修 = 文件入口 strict-load 后、defaults 前跑 canonical/plan 双 schema 校验) + F-PRE-R10-02 (placement generator 闭式几何族硬编码 [core 9x9+6/14, omni 3x3, pole 2x2+radius5, boundary 1x3, long_sides w>h, square w==h] 从不对照 canonical dimensions, schema-valid 漂移可「canonical 说一套 pose 发另一套」; 修 = `_validate_template_geometry_contract()` 分派前 fail-closed) + F-PRE-R10-03 (audit 工件 metadata 过时, 再生)**。r8 已审枚举完备性 (66403 独立重建) 与 ceil 数学 17 操作; r9 已审交叉一致性 12 行矩阵; r10 已审 pose 几何变换数学 (旋转/极性 9 行手算)。**本轮 r11 = R10 修复确认 + 两个未深审角度**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-BIND / F-BL / F-GM / F-RT / F-CUT 系列条款), 这些面各有自己的线, 别在本轮重报。preprocess 链自 r10 修复后零代码变化。

## 审查重点 (按优先级)

### Q1 F-PRE-R10-01/02 修复确认 (攻击面)
① schema 校验加在 path loader (`load_default_preprocess_context` / `load_preprocess_context_from_paths`) — 全仓还有没有**第三个文件入口**绕过这两个 loader 直接 strict-load + 构造 context (scripts/ 与 src/ 都扫)? `lru_cache` 在 `load_default_preprocess_context` 上 — 缓存命中路径与首次路径的校验语义一致吗 (首次失败后再调用会怎样)? ② `_validate_template_geometry_contract()` 的覆盖面 — 它锁的字段集 (dimensions/core_limits/power_coverage_radius/placement_rule) 之外, 还有没有 generator 硬编码消费但 contract 没锁的 canonical 字段 (如 `rotatable` 影响 orientation 枚举? `is_solid_z`?)? 找出每个生成器实际读/隐含假设的字段全集与 contract 锁的字段集对照。③ 两个修复的交互: schema 校验先于 context 构造, geometry contract 在 generate_all_pools 分派前 — placement_generator 自己读 canonical 时走的 loader 有 schema 校验吗 (还是只有 strict JSON)?

### Q2 demand solver 数学本体 (新角度)
`src/preprocess/demand_solver.py` 从 canonical 配方/目标解出 per-operation 需求 (含 cycle groups 方程组)。请独立审数学: ① **从 canonical_rules.json 的 recipes + production_targets 出发, 手工重算完整 demand 链** (目标产物 → 逐级配方展开 → 各 operation 的理论速率需求), 与 demand solver 的输出 (`machine_counts.json` / `generic_io_requirements.json` 的 52/34/18 等数字) 对照 — 任何不一致都是 finding; ② cycle groups 的方程组求解 (square system): 解的存在性/唯一性/非负性是被验证的还是假设的 (非唯一解或负解被静默接受 = 需求工件错)? 方程系数从配方哪里来, 有没有 off-by-one (per-tick vs per-cycle)? ③ ceil 的应用位置: 理论速率 → 整数机器数的取整发生在哪一级 (过早取整会放大误差, 链式 ceil(ceil(x)) 与 ceil(x) 的语义差异) — 实现的取整位置与 specs/04 的规定一致吗?

### Q3 canonical 17-recipe 投影 vs vendored 上游快照保真 (新角度; 审计投影忠实性, canonical 内容本身是 owner-gate 不许改)
`rules/canonical_rules.json` 是从 `third_party_snapshots/` 下的 vendored 上游数据 (JamboChen/endfield-calc 配方+物品 + hsyhhssyy/IndustrialPlanner base 定义) 人工整合的 17-recipe 投影。请抽 5-6 个 recipe (覆盖原料/中间品/终品/cycle group 成员) 与上游快照逐字段对照: ① 配方输入/输出物品与数量、ticks_per_cycle 是否忠实 (单位换算如有, 换算对吗)? ② facility 模板尺寸/端口规则与上游 base 定义一致吗? ③ 不一致处区分「有意的投影决策」(应该已有文档/注释痕迹) vs「无痕迹的漂移」(= finding, 报出来但**不要改 canonical**, 修复属 owner gate)。

## 明确不要报的

- 设计决策本身 (canonical 17-recipe 口径/266/omni_wireless/52-Port, owner 已定 — Q3 审的是投影忠实性不是设计); r1-r10 已修 finding 与已审结论 (重复报不算)。
- binding/master/campaign/scheduler/routing/cuts 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B 禁区; exploratory 不审; commodity_demands.json 不在 hash 闭包 (diagnostic-only 已判)。
- DOC-LOW-01 plan metadata 措辞 (已挂账)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2980 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **冻结工件条款**: 若修复牵涉 candidate_placements 再生或登记 hash 的冻结工件, 交付必须含再生步骤 + 期望 sha256/字节数 + 同批推进的登记位置清单。canonical 内容修改是 owner gate, Q3 发现只报不改。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q2 手算 demand 链与 Q3 抽样对照表。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = R10 修复确认 + demand solver 数学 + canonical 投影保真; 其余面不审。
