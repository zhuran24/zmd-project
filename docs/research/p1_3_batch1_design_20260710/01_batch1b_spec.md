# 批 1B 实现规格书：cov 通道 / witness cell / 容量 / extraction / required 原生化（2026-07-10）

主会话亲写（分工三分法：计划书=主会话）。实现=codex，交付后 opus+codex 双审，主会话终审+reseal。**慢 lane 必跑批**。

## 0. 背景与范围

- 前置：1A 骨架已落地（`b755e80`）：`c1_power_pole_representation` 开关默认 False、`p_k` 池+常量 interval、池完整性五重校验、`c1_power_pole_binding` clone 往返、family count vars。
- 本批：C1 开启时的**覆盖语义**落进生产——cov 通道+witness cell 替换旧 wide-element witness、selected-powered dominance bound、capacity 喂入、extract_solution、required 杆原生化、§九三项前置。
- **开关仍默认 False**（翻默认+canonical env=1D）。默认路径必须 proto 级零变化。
- owner 已拍板（2026-07-10）：旧 witness 编码 certified 层不留 runtime env 对照。**1B 不删旧 witness 函数本体**（等价性测试直调它作参照），但不为它建任何新 env/开关。
- 语义权威：任务书 `00_batch1_workplan.md` §二.7/8/10、§四、§九；原型 `docs/research/p1_3_a_batch0_20260709/c1_encoding_patch.py:146-240`（该语义已被生产破墙 b0_4r OPTIMAL@541s + 独立复验六项全过实证）。

## 1. 手术点（行号为 `b755e80` 后实况）

`src/models/exact_coordinate_master.py`（sealed，本批唯一 sealed 改动文件）：

1. **撤挡板**：`build()` :3691-3692 的 `NotImplementedError("C1 coverage lands in batch 1B")` 撤除；C1+`skip_power_coverage=False` 走新覆盖路径。
2. **dispatch 分流**：coverage 调用点 :3727-3731。新建独立方法 `_add_c1_power_coverage_constraints()`，在调用点按 `self.c1_power_pole_representation` 分流；**不在旧 `_add_geometric_power_coverage_constraints()`（:6262）内部塞 if**——旧函数保持原样（等价测试参照+默认路径零变化）。
3. **非矩形 fail-closed**：C1 witness-cell 仅在 `_supports_rectangular_power_coverage()`（:5576）为真时 sound。C1 开启+非矩形 → `raise NotImplementedError`（信息写明"C1 非矩形回退不在批 1B 范围"）。不迁移 table 编码。
4. **cov 通道**（原型 :168-185 原生化）：全格盘 `cov` 数组按 `flat = cx + cy * grid_w` 顺序（与原型一致）；无 coverer 的 cell `cov == 0`，有 coverer `cov <= sum(p_k covering cell)`（只 `<=` 方向是有意设计——`target == 1` 反推至少一个覆盖杆且不虚报覆盖）。coverage cells 数据用 1A 已校验过的 `power_coverage_cells`（池校验已含几何等式）。
5. **witness cell**（原型 :187-214 原生化）：每 powered slot 建 `wx/wy` 钳 footprint bbox（生产 helper `_slot_footprint_x_start/_y_start/_width/_height`）、`flat = wx + wy * grid_w`、`AddElement(flat, cov, target)`；optional slot → bounds 与 `target == 1` 全部 `OnlyEnforceIf(active)`，mandatory powered → 硬约束。
6. **空池语义**（§九.2，原型 :151-166）：C1 下池空 → 与旧编码逐字对齐：optional powered `active == 0`、mandatory powered `Add(0 >= 1)`（INFEASIBLE）。不允许静默 return 放行。
7. **selected-powered dominance bound**（原型修复 4 :216-240）：生产落位在 `_add_global_valid_inequalities()`（:6346）内按 C1 分流——与旧 residual-slot bound 同位置，保持 valid inequalities 集中一处；**不塞进 coverage 函数**。语义照原型：`Σ p_k ≤ mandatory powered 非杆 + required optional powered 非杆 + Σ residual powered 非杆 active`。
8. **capacity family**：确认 per-template capacity inequalities 在 C1 下由 1A 的 `power_pole_family_count_vars` 照常喂入；若旧代码依赖 residual pole slots 存在才触发，补 C1 分支。
9. **池校验独立锚**（§九.1）：`_validate_c1_power_pole_pool`（:1074）的期望格阵改为**独立推导**：`expected bbox = (0 .. grid_w - tpl_w) × (0 .. grid_h - tpl_h)`，模板尺寸从 template 数据取、**不从池自身的 anchor min/max 推**——"整体均匀缩小但仍完整的格阵"必须被抓住。
10. **单 anchor 单 pose 引理显式化**（§九.3）：池校验中显式断言每 anchor 恰一 pose，注释标注为 C1 等价性引理前提；多 mode 杆出现 → raise（宁拒不放），配测试。
11. **required 杆原生化**（§二.4）：替换 1A 的 required/mandatory 杆 fail-closed raise。required pose optional `power_pole` 进同一 `p_k` 池，语义以现有 required_optional 面为权威（先读 `src/tests/test_exact_coordinate_protocol_bounds.py:117-177` 与 required_optional_slots 构造，等价迁移：钉特定 pose → 对应 `p_k == 1`）。true mandatory power_pole 保持 fail-closed raise（当前工件不存在该形态）。
12. **extract_solution**（:7174）：residual 段后加 C1 段——selected `p_k`（`solver.Value == 1`）输出 `pose_optional::power_pole::<pose_id>` entry，字段与 residual 段**完全同构**（`operation_type="power_supply"`、`bound_type="exact_pose_optional"`、`is_mandatory=False`、`solve_mode` 透传）；required 选中的杆在 C1 下同样从 `p_k` 段输出。不携带 terminal 不认识的新字段（terminal 对未知字段 fail-closed）。
13. **build_stats**：`representation="coordinate_geometric"`、`encoding="c1_pose_bool_cov_channel_v1"`；**保留全部旧 summary 消费字段**（powered_slots/pole_slots/cover_literals/witness_indices/element_constraints/radius——`_master_search_summary` 在读）；新增 `pole_pose_bools`/`cov_channel_literals`/`constant_pole_intervals`/`dominance_bound_terms`。`_finalize_build_stats`（:7068）把 `p_k` 计入可审计字段。

`src/models/master_model.py`：仅当参数链需要透传新配置时改（预期不需要）。

## 2. 测试计划（新文件 `src/tests/test_c1_power_coverage.py` + 扩展 1A scaffold）

1. **C1 vs 旧 witness 小实例等价**（§四.1，本批核心验收）：小 fixture 同一输入分别 build 旧编码与 C1，对比 status + lex 最优值（+小实例可行集投影）。≥4 组，覆盖：mandatory powered 硬约束、optional powered active guard、无 coverer 时禁用、ghost no-overlap 交互、capacity family count、required 杆。
2. **池校验独立锚**：构造"均匀缩小但完整"的池（如只覆盖 [0,50]² 格阵）→ 必须 raise（1A 版会漏过，1B 版必须抓住——这是 §九.1 的回归钉）。
3. **空池 fail-closed**：mandatory powered+空池 → INFEASIBLE；optional powered+空池 → 全禁用但可行。
4. **多 mode 杆** → raise。
5. **extract**：selected `p_k` entries 逐字段过 `_is_authorized_exact_pose_optional_solution_entry`（直接 import 校验）；未选 `p_k` 不出现；required 杆 entry 语义与旧编码一致。
6. **build_stats 兼容**：新 encoding 出现、旧字段全在。
7. **回归**：1A scaffold 13 测、dedup 6 测、protocol_bounds、step_8 全绿。

## 3. 禁碰面

- `benders_loop.py` / `outer_search.py` / `exact_campaign.py` / checker / manifest / allowlist / strong-status：**一律不碰**（剪杆=1C、canonical env=1D、义务层=1E）。
- 默认路径（`c1_power_pole_representation=False`）proto 级零变化——双审必验项。
- 旧 witness 函数本体不删不改。
- 不新增任何 env；不触碰 `EXACT_*` 面。
- 不做 git 操作；不改 proof pins（reseal 由主会话终审后做）。

## 4. 完成判据

- 全部新测+回归绿；命令统一 `.venv/bin/python -m pytest -p no:randomly --basetemp=.pytest_tmp/b1b <files> -q`。
- `.venv/bin/python -m ruff check` 改动文件绿。
- 报告：改动文件清单、每个手术点的落位说明、测试尾部输出、任何偏离规格之处显式列出。
