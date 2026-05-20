# src/adapters/

外部系统适配层 — 把项目的内部数据 (placement_solution / canonical_rules / proof_summary 等) 翻译成下游消费方 (上游游戏数据库 / 第三方 planner / dige viewer 等) 期待的格式; 或反过来从上游摄取数据并 normalize 进项目.

**这一层是 postprocess-only**, 不重定义 solve schema, 也不参与 certified path 严格性 (per PROJECT_LOCK). 改 adapter 不需要 lock update.

---

## 4 个子目录各干嘛

### `industrial_planner/` — IndustrialPlanner (hsyhhssyy/IndustrialPlanner v2 web app) 适配 (10 文件)

主流 adapter, 双向. 把项目 blueprint 导出成 IP v2 能 import 的格式 + 验证 IP v2 blueprint 静态 / 物料平衡.

| 文件 | 作用 |
|---|---|
| `export_blueprint.py` | 项目 → IP v2 蓝图导出 (主入口) |
| `blueprint_validator.py` | IP v2 蓝图静态校验 (无 LP, 跟 IP v2 web app validator 对齐) |
| `commodity_resolver.py` | 项目 commodity → IP v2 item 解析 |
| `recipe_matcher.py` | 项目 recipe → IP v2 recipe 匹配 |
| `deployment_transform.py` | 部署 / 外部 base 适配 (future_scope, 当前 valley4_protocol_core only) |
| `mapping_registry.py` | typeId / facility_type 映射注册表 |
| `compatibility_report.py` | 兼容性 report 生成 |
| `throughput_audit.py` | 吞吐量审计 (与 IP v2 LP solver 对齐) |
| `base_registry.json` | base 数据 (从 third_party_snapshots/industrial_planner/bases/ 派生) |
| `device_type_registry.json` | device typeId 数据 (从 IP v2 registry.ts 派生) |

**首选 adapter, 生产 release 用这条线**. 大部分对接工作在这.

### `endfield_calc/` — JamboChen/endfield-calc (TypeScript 游戏数据库) 适配 (6 文件)

单向, 上游 → 项目. 把 endfield-calc 的 items.ts / recipes.ts / facilities.ts 摄取进项目, normalize 后用于 canonical_rules 派生.

| 文件 | 作用 |
|---|---|
| `typescript_snapshot.py` | 读 third_party_snapshots/endfield_calc/typescript_fixture/*.ts |
| `snapshot_ingest.py` | 从 raw TS snapshot 摄取到 normalized catalog |
| `normalize_catalog.py` | 规范化到 NormalizedCatalog (跟 src/interchange 对接) |
| `semantic_mapping.py` | endfield-calc item/recipe → 项目语义对齐 (17-recipe canonical projection 的源头) |
| `diff_report.py` | 上游版本 diff 报告 (refresh 时 produced) |
| `provenance.py` | 数据 provenance 记录 |

**通过 `scripts/refresh_endfield_calc_snapshot.py` mechanical sync**. 改 canonical_rules.json 是手动决定 (PROJECT_LOCK gate), 不是 adapter 自动做的.

### `dige/` — Dige 内部 viewer 适配 (1 文件)

| 文件 | 作用 |
|---|---|
| `result_view_models.py` | 把项目 result → dige viewer 能渲染的 view model |

**仅 1 文件**, 比较小. 是历史适配, 用得不多.

### `base_planner/` — outer deployment planner 适配 (2 文件, future_scope)

| 文件 | 作用 |
|---|---|
| `outer_deployment_plan.py` | 外部部署 plan (跨 base 拼接) |
| `report_shapes.py` | 报告 shape 定义 |

**`future_scope`** — 当前 active 只跑 valley4_protocol_core 70×70 单 base, base_planner 是未来多 base 部署的占位.

---

## adapter 数据流向

```
endfield-calc TS files (上游)
  ↓ third_party_snapshots/endfield_calc/typescript_fixture/  (vendor)
  ↓ src/adapters/endfield_calc/typescript_snapshot.py        (摄取)
  ↓ src/adapters/endfield_calc/normalize_catalog.py          (规范化)
  ↓ src/interchange/normalized_catalog.py                    (统一类型)
  ↓ rules/canonical_rules.json                               (语义对齐, 手动 gate)
  ↓ src/preprocess/...                                       (派生 frozen artifacts)
  ↓ data/preprocessed/mandatory_exact_instances.json 等       (solver input)

项目 solve → placement_solution
  ↓ src/io/serializer.py                              (blueprint JSON v2)
  ↓ src/adapters/industrial_planner/export_blueprint.py (IP v2 格式)
  ↓ src/adapters/industrial_planner/blueprint_validator.py (静态校验)
  ↓ data/exports/industrial_planner/                  (交付)
  → IP v2 web app import → 玩家手动验证
```

---

## 哪个 adapter 是"首选"

| 用途 | 首选 |
|---|---|
| 上游游戏数据摄取 | `endfield_calc/` |
| 项目蓝图交付到 web app | `industrial_planner/` |
| 蓝图校验 / 物料平衡 | `industrial_planner/blueprint_validator.py` + IP v2 LP solver (在 `scripts/`) |
| 内部 viewer 渲染 | `dige/` (用得少) |
| 未来跨 base 部署 | `base_planner/` (future_scope, 暂不用) |

**Phase 3A delivery 主要走 `industrial_planner/`**, 这是当前 active surface.

---

## 跟 `src/interchange/` 的关系

`src/interchange/` 是**类型契约层**, 定义 PreprocessContext / NormalizedCatalog / TargetCapabilities 等 Schema. adapter 把外部数据转成 interchange 类型, interchange 再喂给 solver. 不要在 adapter 自己定义类型, 用 interchange 的.

---

## 不动 certified path

adapter 改动 **不需要** update PROJECT_LOCK / FILE_STATUS / spec, 也不进 preflight gate 的 hash 校验列表. 但**不能**:
- 重定义 canonical_rules.json (那是 PROJECT_LOCK gate)
- 改变 candidate_placements.json / mandatory_exact_instances.json (frozen)
- 把 exploratory 路径的输出当 certified 蓝图导出

详见 `PROJECT_LOCK.md` "Forbidden Changes" 段.
