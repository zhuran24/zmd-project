# band22 见证布局 → IndustrialPlanner 蓝图导出

**状态**：已完成（2026-08-05）。产物为 research-only 导出件，不是认证材料，不参与任何 release 边界判定。

把 band22 见证布局（`max_lex = (42, 6)` 的 6×7 空矩形候选）转成 IndustrialPlanner 网页模拟器
（<https://endfield.anonymous-test.top>，上游 `hsyhhssyy/IndustrialPlanner`）可导入的蓝图 JSON，
供 owner 在网页端目视检查并试跑仿真。

---

## 成品

| 项目 | 值 |
| --- | --- |
| 蓝图文件 | `.artifacts/band22_sim_export_20260805/band22_industrial_planner_blueprint_20260805.json` |
| owner 取用副本 | `~/下载/band22_industrial_planner_blueprint_20260805.json` |
| sha256 | `d040502ddcff28af166a8798a52b1b044d7f37ef6e26f5a534b2009fb1e394ec` |
| 设备数 | 1,433（290 建筑 + 1,143 传送组件） |
| baseId | `valley4_protocol_core`（70×70） |
| blueprintVersion | `1`（schema `industrial-planner-blueprint`，version `1.0`） |

同目录下另有：

- `export_summary.json` —— 全部统计口径（含流向修正前后的对比数字）
- `validation_report.json` / `.md`、`validation_errors_full.json` —— 离线校验产出
- `hub_attribution_verdict.json`、`hub_attribution_errors_as_shipped.json`、`registry_without_hub/`
  —— 把校验错误归因到地基枢纽的机器证据
- `band22_canonical_blueprint.intermediate.json` —— canonical 中间件，供后续 schema v3 重导出复用
- `stock_exporter_output_no_flow_correction/` —— 未加流向修正的导出器原始产出，仅作对照
  （**不要拿它导入**，见下文流向修正一节）
- `preflight.log` —— 本次提交的 staged 门禁日志

---

## 导入操作步骤

1. 在网页端选择 **四号谷地 · 协议核心区**（`valley4_protocol_core`）基地。
2. 导入 `band22_industrial_planner_blueprint_20260805.json`。
3. **把协议枢纽（9×9）从默认的 (0,0) 拖到 (60,36)。** 这一步必须手动做：蓝图格式没有任何字段能表达
   枢纽位置，导出器也不会为它生成设备。band22 设计把协议核心放在 anchor (60,36)，而基地默认把枢纽
   放在左下角 (0,0)-(8,8)，那 81 格在本设计里是边界口和机器。不移动枢纽，这 81 格会与枢纽重叠。
4. 移动后再跑仿真。

枢纽在游戏内可移动（上游基地定义把它标为 `movable: true`），所以第 3 步是网页端的正常操作，不是绕过校验。

---

## 输入与可复现命令

两个输入都是只读的：

- **官方位姿** `.artifacts/w0_fixrerun_20260804/band22_alignment/registration_placement_solution.json`
  —— 291 条（266 mandatory 设施 + 25 电杆），每条带 `pose_idx`。
- **设计见证** `docs/research/cleanroom_rederivation_20260718/27_band22_witness_delivery_20260804/band22_repaired_design_witness_not_checker_schema.json`
  —— 628 个激活端口 + 1,143 个传送组件。

几何权威是冻结候选池 `data/preprocessed/candidate_placements.json`
（54,467,709 字节，sha256 `f05b1291…`，脚本启动时逐字节校验），**不是见证**：每个设施的占格与端口格
都从 `pose["occupied_cells"]` / `pose["*_port_cells"]` 读出。见证只提供池里没有的信息——哪些端口激活、
端口商品、以及传送网络。

```bash
# 生成蓝图（默认带流向修正，见下节）
env -u PYTHONPATH -u PYTHONHOME .venv-uvbolt-backup/bin/python \
  docs/research/band22_sim_export_20260805/build_band22_ip_blueprint.py \
  --out-dir .artifacts/band22_sim_export_20260805 \
  --blueprint-filename band22_industrial_planner_blueprint_20260805.json

# 把 82 条校验错误逐条归因到地基枢纽
env -u PYTHONPATH -u PYTHONHOME .venv-uvbolt-backup/bin/python \
  docs/research/band22_sim_export_20260805/verify_hub_is_sole_blocker.py \
  --blueprint .artifacts/band22_sim_export_20260805/band22_industrial_planner_blueprint_20260805.json \
  --out-dir .artifacts/band22_sim_export_20260805
```

转换脚本用仓库自己的库函数（`build_industrial_planner_export_bundle` /
`validate_industrial_planner_blueprint` / `resolve_facility_device` / `resolve_routing_device`），
只在内存里拼 canonical `optimal_blueprint.json` 形状喂给它，不写 `data/` 下任何路径。
任何映射不上的设施类型、传送类型、端口种类、外形不符，一律抛异常，不静默丢弃。

---

## 传送组件流向修正（本次导出对导出器默认行为的唯一偏离）

**现象**：直接用导出器输出的蓝图，1,143 条设计传送连接里只有 199 条方向正确，356 条方向反了，
588 条根本连不上——网页端点仿真不会有物料流动。

**原因有两层，都在 `src/adapters/industrial_planner/mapping_registry.py`：**

1. **y 轴约定相反。** canonical/见证是 y 向上（`src/models/routing_subproblem.py:27` 的
   `DIR_DELTA` 里 `N=(0,+1)`），IndustrialPlanner 侧是 y 向下（校验器
   `blueprint_validator._boundary_key` 把 (x,y) 的 N 边和 (x,y-1) 的 S 边配成同一条边界）。
   `resolve_routing_device` 直接把 canonical 方向名当成 IP 边名用，坐标却原样透传，两者对不上。
2. **直belt 丢掉流向。** `resolve_routing_device` 给直线传送带的旋转只按**轴**取值
   （E-W 取 0，N-S 取 90），完全不区分物料往哪边走；而 IP 的 `belt_straight_1x1` 在旋转 0 时
   固定 `in_w` / `out_e`。转弯同理按无序方向对取值，`item_log_converger` 的出口在旋转 0 时位于 W 边、
   `item_log_splitter` 的入口在 E 边，与 `_DIRECTION_TO_ROTATION` 差 180°。

**修正**：脚本在导出器产出蓝图之后加一道后处理，**只改传送设备的 `typeId` 与 `rotation` 两个字段**，
取那个「旋转后的端口边正好复现设计 flow_in/flow_out」的唯一选择，方向名按 `N↔S` 翻转、坐标不动
（坐标透传是边界口能贴上基地总线带的前提）。设备族取自同一份静态注册表，没有硬编码几何。
找不到满足的 (typeId, rotation) 就抛异常。

**效果**（`export_summary.json` 里 before/after 两组数字）：

| 指标 | 修正前 | 修正后 |
| --- | --- | --- |
| 设计传送连接 | 1,143 | 1,143 |
| 方向正确 | 199 | **1,143** |
| 方向反了 | 356 | 0 |
| 完全没连上 | 588 | 0 |
| 校验器 port warnings | 159 | **0** |

改动量：785 个旋转、4 个类型（逆时针↔顺时针转弯）。1,143 条全部复现，是这次修正方向正确的机器证据。

坐标透传意味着蓝图在屏幕上相对游戏内视角是上下镜像的；连接结构与仿真语义不受影响。

**这层修正只在本研究脚本里，没有改适配器。** 上游 schema v3 升级线若要复用，需要把同样的语义
落进 `mapping_registry`——那属于那条线的范围。

---

## 映射决策清单

### 设施（290 个设备）

| canonical 类型 | 数量 | 目标 typeId | 依据 |
| --- | --- | --- | --- |
| `manufacturing_3x3` | 132 | `item_port_grinder_1` 69、`item_port_furnance_1` 51、`item_port_shaper_1` 6、`item_port_cmpt_mc_1` 6 | 走 `resolve_facility_device_precise` 的配方精确解析，非兜底 |
| `manufacturing_5x5` | 49 | `item_port_planter_1` 32、`item_port_seedcol_1` 17 | 同上 |
| `manufacturing_6x4` | 38 | `item_port_thickener_1` 32、`item_port_filling_pd_mc_1` 3、`item_port_tools_asm_mc_1` 3 | 同上 |
| `boundary_storage_port` | 46 | `item_port_unloader_1` | 46 个全是纯输出口 → 卸货器；带 `pickupItemId` 配置 |
| `power_pole` | 25 | `item_port_power_diffuser_1` | 2×2 直接对应 |
| `protocol_core` | 1 | —— 不产出设备 | 导出器固定行为：IP 用 `baseId` 表达基地本体。**这是需要手动拖枢纽的根源** |

219 台机器的解析模式全部是 `precise`（配方精确解析到真实设备类型），零 generic 兜底、零商品翻译失败；
46 个边界口与 25 个电杆是 `direct`，协议核心是 `dropped`。导出器全程只产生 1 条 warning，即上面
protocol_core 那条。

外形逐个核对过：每个设施的 IP 设备旋转后尺寸必须与冻结池里的占格外形逐格相等，否则抛异常。
边界口的 3×1 外形靠 `boundary_storage_port` 映射自带的 `rotation_offset_degrees=90` 对上
（bottom 口 orientation 1 → 旋转 180，left 口 orientation 0 → 旋转 90）。

### 传送组件（1,143 个设备）

| 见证 kind | 数量 | canonical 类型 | 目标 typeId |
| --- | --- | --- | --- |
| `straight` | 596 | `belt` | `belt_straight_1x1` |
| `merger` | 274 | `merger` | `item_log_converger` |
| `splitter` | 257 | `splitter` | `item_log_splitter` |
| `turn` | 16 | `belt` | `belt_turn_ccw_1x1` 12 / `belt_turn_cw_1x1` 4 |

canonical schema 的合法组件类型只有 `belt` / `splitter` / `merger` / `bridge`，
所以 `straight` 和 `turn` 都落成 `belt`，直/弯由 `flow_in`∪`flow_out` 还原，没有信息损失。
本设计不含 bridge，`L1_elevated` 层为空。

### 传送组件的商品

见证不带逐格商品，所以每格填 canonical schema 自己的未知商品哨兵 `[TBD]`。
这不影响任何导出结果：导出器从商品只推导一件事——走传送带族还是管道族；
脚本启动时机器校验见证全部 19 种商品都不是液体类（`is_liquid_like_commodity` 全 False），
所以哨兵不可能改变任何一个设备的选型。传送设备本身不带 config 字段。

---

## 离线校验结论

以仓库自带校验器 `validate_industrial_planner_blueprint` 为准：

```
is_import_compatible : true      ← schema / 注册表 / 地块边界 / 放置规则全过
is_layout_healthy    : false     ← 81 条 overlap + 1 条 port mismatch
port_warnings        : 0
device_count         : 1433      占格 5,298   地块利用率 96.04%
```

**82 条错误 100% 归因于地基协议枢纽**，已机器验证（`hub_attribution_verdict.json`）：
把 `valley4_protocol_core` 的地基里那一条 `item_port_sp_hub_1` 去掉后重跑同一个校验器，
错误数 **82 → 0**，`is_layout_healthy` 与 `is_clean` 全部转 true。除这一条外注册表未作任何改动。

这是**已知语义、不是本次导出的缺陷**：仓库自带同型负向 fixture
`data/examples/industrial_planner/minimal.foundation_conflict.industrial_planner.blueprint.json`
与测试 `src/tests/test_industrial_planner_validator.py::test_foundation_conflict_fixture_fails_overlap_audit`，
钉的正是「压到地基 → `is_import_compatible` 仍为 true、`is_layout_healthy` 为 false」。蓝图能被网页端导入。

**并且这条地基枢纽本身的可信度存疑。** 校验器注入的枢纽只来自
`src/adapters/industrial_planner/base_registry.json` 的 `metadata.generated_at = 2026-03-28` 快照——
仓库里三套 IP 上游 pin 中最旧、且是唯一没有 commit 钉的一套。更新的 vendored 快照
`third_party_snapshots/industrial_planner/base-definition.master.ts`（commit `dd334ed5`，vendored 2026-07-18）
里，`createValley4ProtocolCoreBuiltinEntities()` 只构造总线源桩 + 18 段总线，位置全在负坐标
（x=-4 或 y=-4，即 70×70 可放置区之外），**根本没有枢纽**。按 rules-audit SOP 的权威顺序
（owner 游戏实测 > dd334ed5 快照 > 本地注册表快照），本地那套是最低一级。

历史上仓库里所有 checked-in 蓝图都主动让空 (0,0)-(8,8) 那 81 格（`benchmark.full70x70` 实占 3,575 格、
利用率约 73%），这是隐性惯例，从未写成规则。本次导出是第一份真正铺满 70×70 的蓝图（利用率 96.04%）。

### 空矩形里的 22 格传送带

6×7 ghost 矩形位于 `[1,6]×[51,57]`。**42 格内零设施本体**（脚本硬校验，不满足就抛异常）；
但有 **22 格传送带穿过**。这符合仓库的 ghost 语义——`PROJECT_LOCK.md` 谓词 (1) 只要求
`all_cells(π) ∩ R = ∅`，只管设施本体，传送组件不算占用者
（旁证见 `.artifacts/w0_fixrerun_20260804/band22_alignment/max_empty_rect_for_this_placement.json`
的 `authority_for_ghost_only_avoids_bodies`）。删掉这 22 格会切断见证的路由连通性，所以照实导出。
网页端目视时那 6×7 区域会看到传送带，这是设计本身如此，不是导出偏差。

---

## 上游漂移风险

蓝图按仓库 pin 的 v1 格式产出（顶层只写 `schema` / `id` / `version` / `name` / `createdAt` /
`baseId` / `devices` / `blueprintVersion` 八个字段，加任何自定义字段导出器不写、校验器不读、上游无消费点）。
上游有 1→2→3 的 legacy 迁移链，v1 能导入。

真正的验收是 owner 实际导入。离线校验只证明蓝图与仓库那三份静态注册表快照一致，而这些快照
（设备几何 `generated_at 2026-03-28`、基地字段子集 observed 2026-05-07、实体定义 commit `dd334ed5`
vendored 2026-07-18）互不同源、日期跨度三个半月，已知至少 `outerRing` 一项在两版间矛盾
（本地 4/2/2/4 vs 上游 5/5/5/5，且 owner 实测 70×70 外不能放任何东西）。网页端在 `dd334ed5` 之后
仍可能继续演进。
