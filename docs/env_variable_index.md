# Environment Variable Index

**项目 `EXACT_*` / `PHASE3B_*` env 变量索引**（坐标-master / Phase 3B 时代为主）。

**最后更新**: 2026-05-16（坐标-master 时代）

> ⚠️ **(2026-06-04) 本索引不完整，勿当 "不用 grep" 的权威全集**：它早于 **cut-family LBBD / B1 pose-bool / Design A-B** 时代，**未收录**这些时代的 env。要全集请 grep 源码（`os.environ` / `getenv` 抓 `EXACT_`）+ 看 `CLAUDE.md` runbook 的 env 表（PCR-CUT / community-hint / cache-trio spike 等段）。已知**未收录**的主要 env 组（权威 Type / Reader / Default 以源码为准，此处只列名提示存在）：
> - **B1 pose-bool master**：`EXACT_USE_POSE_BOOL_MASTER`（核心切换）
> - **PCR-CUT / B1 routing**：`EXACT_B1_PATCH_ROUTING_CORE`(+`_TOP_K`/`_SECONDS`/`_PER_PATCH_SECONDS`/`_MAX_CELLS`/`_QX_CAP`)、`EXACT_B1_LAZY_DEMAND_CUT`、`EXACT_B1_PORT_CLEARANCE_HARD`、`EXACT_B1_SEPARATOR_HULL*`、`EXACT_B1_ROUTING_AWARE_BINDING`、`EXACT_B1_D2_COMMODITY_FLOW`、`EXACT_B1_BYPASS_ROUTING_PRECHECK`、`EXACT_B1_DELETION_CORE_CUT`、`EXACT_B1_ITER_ON_ROUTING_INFEASIBLE`、`EXACT_B1_BINDING_ALT_CAP`、`EXACT_B1_ABSTRACT_ROUTING_*`
> - **cut-family**：`EXACT_FAMILY_VALIDATOR_STRICT`、`EXACT_F3_GENERATOR_ENABLED`、`EXACT_F7_GENERATOR_ENABLED`、`EXACT_F8_GENERATOR_ENABLED`、`EXACT_GHOST_CONDITIONED_FAMILY_BOUNDS_ENABLED`
> - **其它**：`EXACT_COMMUNITY_BLUEPRINT_HINT_PATH`、`EXACT_SUBPROBLEM_REPEAT_PROBE`、`EXACT_LAZY_POWER_COMPLETION`、`EXACT_SMT_MT_OUTER_PRUNING`、`EXACT_USE_PORT_ACTIVE`、`EXACT_D2_CP_SAT_WORKERS`、`EXACT_PATCH_ROUTING_CP_SAT_WORKERS`
>
> **另**：下方 Reader 列里的 `phase3b_*` 文件路径在 2026-05-16 cleanup（commit `e4bad28`）后已重组到 `src/search/phase3b/<cluster>/<short>.py`（前缀剥离），旧 `src/search/phase3b_*.py` 路径**已失效**。

---

## 怎么读这份文档

每条 env 列:
- **Name**: env 名字 (设置时用)
- **Type**: bool / int / float / str / path / json
- **Default**: 不设时的默认行为
- **Reader**: 哪个源文件读它 (跟着 grep 能找完整 logic)
- **作用**: 一句话讲清干嘛

每个分组以**实际用法的影响维度**分类, 不按字母. 想找"控制 worker 数的" 一眼看到一组.

---

## A. Worker / 并行控制 (RAM 跟搜索深度 trade-off)

| Name | Type | Default | Reader | 作用 |
|---|---|---|---|---|
| `EXACT_MASTER_CP_SAT_WORKERS` | int | 8 | master_model.py | master.solve 内部 CP-SAT 并行 worker 数. 减 RAM peak. 1 = 12.78 GiB, 8 = 30 GiB |
| `EXACT_BINDING_CP_SAT_WORKERS` | int | 4 | cp_sat_worker_config.py | binding subproblem CP-SAT worker |
| `EXACT_ROUTING_CP_SAT_WORKERS` | int | 8 | cp_sat_worker_config.py | routing subproblem CP-SAT worker |
| `EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS` | int | 8 | cp_sat_worker_config.py (`DEFAULT_LOCAL_CAPACITY_CP_SAT_WORKERS=8`) | local power capacity 子求解器 CP-SAT worker |
| `EXACT_CP_SAT_WORKERS` | int | (auto) | cp_sat_worker_config.py | fallback default for all CP-SAT calls if specific missing |
| `EXACT_PARALLEL_PROCESSES` | int | main.py -p 默认 1 / readiness gate 缺省 4 | run_campaign_linux.sh → readiness gate (`production_readiness_gate.py`) | 外层 outer_search 并行 process 数 (-p flag mirror; **两处真实 default 不同**) |

---

## B. 时间 / 超时预算

| Name | Type | Default | Reader | 作用 |
|---|---|---|---|---|
| `EXACT_LOCAL_CAPACITY_CP_SAT_MAX_SECONDS` | float | (内部 default) | master_model.py | local power capacity 单次 solve 超时 |
| `EXACT_POWER_SUBPROBLEM_SECONDS` | float | (内部 default) | benders_loop.py | power placement subproblem 超时 |
| `EXACT_GHOST_AWARE_COORDINATE_VALIDATION_SECONDS` | float | (内部 default) | phase3b_coordinate_validation_*.py | coordinate validation 单次预算 |
| `EXACT_GHOST_AWARE_POSE_ORDER_VALIDATION_SECONDS` | float | (内部 default) | phase3b_pose_order_validation_probe.py | pose order validation 单次预算 |
| `EXACT_MANDATORY_RECTANGLE_PRECHECK_TIME_BUDGET_SECONDS` | float | 2.0 | `master_model.py` | mandatory rect precheck CP-SAT 32-anchor 超时 |

---

## C. Master CP-SAT 内部调优

控制 OR-Tools `solver.parameters` 各字段, 改了等于改 CP-SAT 内部算法的开关.

| Name | Type | Default | Reader | 作用 |
|---|---|---|---|---|
| `EXACT_MASTER_CP_MODEL_PRESOLVE` | int (0-3) | (CP-SAT default) | master_model.py | CP-SAT presolve 强度 |
| `EXACT_MASTER_CP_MODEL_PROBING_LEVEL` | int (0-3) | (CP-SAT default) | master_model.py | presolve probing 强度 |
| `EXACT_MASTER_SYMMETRY_LEVEL` | int (0-4) | (CP-SAT default) | master_model.py | symmetry breaking 强度 |
| `EXACT_MASTER_LINEARIZATION_LEVEL` | int (0-2) | (CP-SAT default) | master_model.py | constraint linearization 强度 |
| `EXACT_MASTER_TABLE_COMPRESSION_LEVEL` | int | (CP-SAT default) | master_model.py | table constraint 压缩 (新参数) |
| `EXACT_MASTER_LINEAR_SPLIT_SIZE` | int | (CP-SAT default) | master_model.py | linear constraint 拆分阈值 |
| `EXACT_MASTER_CLAUSE_CLEANUP_PERIOD` | int | (CP-SAT default) | master_model.py | 学到的 clause 清理周期 |
| `EXACT_MASTER_NO_OVERLAP_2D_AREA_ENERGETIC` | bool | (CP-SAT default) | master_model.py | no_overlap_2d energetic reasoning |
| `EXACT_MASTER_NO_OVERLAP_2D_TIMETABLING` | bool | (CP-SAT default) | master_model.py | no_overlap_2d timetabling propagator |
| `EXACT_MASTER_NO_OVERLAP_2D_TRY_EDGE` | bool | (CP-SAT default) | master_model.py | no_overlap_2d try-edge propagator |
| `EXACT_MASTER_USE_STRONG_DISJUNCTIVE_PROPAGATION` | bool | (CP-SAT default) | master_model.py | strong disjunctive propagator |
| `EXACT_MASTER_PRESOLVE_EXTRACT_INTEGER_ENFORCEMENT` | bool | (CP-SAT default) | master_model.py | presolve extract integer enforcement |
| `EXACT_MASTER_IGNORE_LP_SUBSOLVERS` | bool | (CP-SAT default) | master_model.py | 关闭 LP subsolver portfolio |
| `EXACT_MASTER_SEARCH_BRANCHING` | str | "AUTOMATIC" | master_model.py | search branching strategy |
| `EXACT_MASTER_RANDOM_SEED` | int | 0 | master_model.py | CP-SAT random seed (固定 reproducibility) |
| `EXACT_MASTER_RANDOM_SEED_BASE` | int | (varies) | benders_loop.py | per-iteration seed base |
| `EXACT_MASTER_FILL_TIGHTENED_DOMAINS` | bool | False | master_model.py | 跨 solve 传 dual info / tightened domains |
| `EXACT_MASTER_CP_SAT_LOG_HEARTBEAT_LINES` | int | 0 | benders_loop.py | master.solve 心跳日志最大行数 |
| `EXACT_MASTER_CP_SAT_LOG_HEARTBEAT_MAX_CHARS` | int | (内部) | benders_loop.py | 单行最大字符数 |

---

## D. Hint 注入 / Warm-start

| Name | Type | Default | Reader | 作用 |
|---|---|---|---|---|
| `EXACT_COMMUNITY_BLUEPRINT_HINT_PATH` | path | (empty) | `benders_loop.py` (搜符号, 行号会漂) | **2026-05-16 land**. JSON 路径, 内容 `Dict[instance_id, pose_idx]`. 整链 merge greedy hint, master.solve 用. wrapper 自动 default 指 `data/hints/blueprint_2026_05_13_master_hint.json` |
| `EXACT_MASTER_HINT_CONFLICT_LIMIT` | int | (内部 default) | master_model.py | hint conflict 时的尝试限制 |
| `EXACT_MASTER_HINT_PERSISTENCE` | bool | False | master_model.py | hint 跨 Benders iter 持久化 |
| `EXACT_WARM_START_FAILED_ANCHOR_SAMPLE_LIMIT` | int | (内部 default) | master_model.py | failed warm-start anchor sample 上限 |

---

## E. 优化路径开关 / Search strategy

| Name | Type | Default | Reader | 作用 |
|---|---|---|---|---|
| `EXACT_POWER_PLACEMENT_SUBPROBLEM` | bool | **0** | benders_loop.py | **exploratory-only 守卫**. =1 时 production gate hard block, certified path 拒绝启动. 见 PROJECT_LOCK |
| `EXACT_OUTER_SKIP_UNKNOWN` | bool | 0 | outer_search.py:492 | UNKNOWN candidate 不停 campaign, 跳下一个. P2 #14 数据收集 A 方案 |
| `EXACT_EPSILON_STAGE1_END_HOURS` | float | 25 | outer_search.py | ε-certified stage 1 边界 (起到 25h) |
| `EXACT_EPSILON_STAGE2_END_HOURS` | float | 75 | outer_search.py | ε-certified stage 2 边界 (25h 到 75h) |
| `EXACT_FRONTIER_PROBE_MAX_ANCHORS` | int | 64 | outer_search.py | 前沿探针最大 anchor 数 |
| `EXACT_USE_HIGHS_MASTER` | bool | 0 | `highs_candidate_evaluator.py` (+ highs_master_model.py dead) | 切到 HiGHS master 后端 (实验, 已 verify 死路, 见 lever_verdicts.md L2) |
| `EXACT_MASTER_GHOST_ANCHOR_FILTER` | str | (空) | `benders_loop.py` (`_parse`, ~L417/427) | A 方案 ghost_anchor_filter：`'x,y'` anchor pair（`;` 分隔，如 `22,28`），env-gated, -80% search space |
| `EXACT_POLE_SLOT_UPPER_BOUND_OVERRIDE` | int | (内部) | exact_coordinate_master.py | tight pole_slot upper bound override (#84) |
| `EXACT_COORDINATE_MASTER_SEARCH_PROFILE` | str | "exact_coordinate_guided_branching_v4" | exact_coordinate_master.py | 3 选 1: `guided_branching_v4` / `ghost_first_v1` / `ghost_after_counts_v1` |
| `EXACT_COORDINATE_MASTER_SEARCH_PROFILES` | json | (内部) | exact_coordinate_master.py | profile 切换允许列表 |

---

## F. 守卫 / Readiness gate

| Name | Type | Default | Reader | 作用 |
|---|---|---|---|---|
| `EXACT_GATE_WORKER_PEAK_RSS_GIB` | float | 30 | production_readiness_gate.py:350 | 单 worker RSS peak 上限假设, OOM headroom 公式输入. workers=1 时设 14, workers=8 时设 35 |
| `EXACT_HASH_FILES` | str (list) | (内部) | preflight_gate.py | 冻结制品 hash 校验列表 |
| `EXACT_INSTANCES_PATH` | path | (内部) | (preflight_gate.py?) | mandatory_exact_instances.json 路径 (test override) |
| `EXACT_MODE_FILES` | str (list) | (内部) | preflight_gate.py | exact/exploratory 隔离扫描文件列表 |
| `EXACT_REQUIRED_ARTIFACTS` | str (list) | (内部) | (gate?) | 必需 artifact 文件列表 |
| `EXACT_CERTIFIED_NOTE` | str | (内部) | (campaign / blueprint?) | certified blueprint metadata note |

---

## G. Precheck / Guard advisory

| Name | Type | Default | Reader | 作用 |
|---|---|---|---|---|
| `EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS` | int | (内部 default) | phase3b boundary port precheck | boundary port precheck max anchor |
| `EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS` | int | 32 | benders_loop.py | mandatory rect precheck anchor 数 |
| `EXACT_MANDATORY_RECTANGLE_PRECHECK_WITNESS_MIN_SURVIVORS` | int | (内部) | benders_loop.py | precheck witness 最小存活数 |
| `EXACT_PRE_MASTER_ANCHOR119_MIXED_LANE_GUARD_ADVISORY` | bool | 0 | benders_loop.py | anchor119 mixed lane guard advisory enable |
| `EXACT_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_MAX_ANCHORS` | int | (内部) | benders_loop.py | pre-master coordinate validation max anchor |
| `EXACT_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_SECONDS` | float | (内部) | benders_loop.py | pre-master coordinate validation 超时 |
| `EXACT_PRE_MASTER_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS` | int | (内部) | benders_loop.py | pre-master mandatory rect precheck anchor 数 |
| `EXACT_GHOST_OVERLAP_FORCED_DOMAIN_PRECHECK` | bool | (内部) | phase3b probe | ghost overlap forced domain precheck enable |
| `EXACT_GHOST_Y_OVERLAP_FORCED_LABEL_PRECHECK` | bool | (内部) | phase3b probe | ghost Y overlap forced label precheck enable |
| `EXACT_SAME_X_STRIP_FIXED_GHOST_CAPACITY_PRECHECK` | bool | (内部) | phase3b probe | same X strip fixed ghost capacity precheck enable |
| `EXACT_SIGNATURE_MONOTONIC_FORCED_LABEL_PRECHECK` | bool | (内部) | phase3b probe | signature monotonic forced label precheck enable |
| `EXACT_GHOST_AWARE_COORDINATE_VALIDATION_MAX_ANCHORS` | int | (内部) | phase3b coordinate validation | max anchor for coordinate validation |

---

## H. Subproblem / Binding 配置

| Name | Type | Default | Reader | 作用 |
|---|---|---|---|---|
| `EXACT_BINDING_USE_OVERLOAD_SEPARATION` | bool | 0 | binding_subproblem.py | binding overload separation (multi-occur cut) |
| `EXACT_BINDING_DUMP_STATE` | bool | 0 | binding_subproblem.py | binding 调试 state dump (开发用) |
| `EXACT_SUBPROBLEM_MAX_MEMORY_MB` | int | (内部) | cp_sat_worker_config.py | subproblem 内存 cap |
| `EXACT_SUBPROBLEM_PARAMS` | json | (内部) | cp_sat_worker_config.py | subproblem CP-SAT 参数 override |
| `EXACT_SUBPROBLEM_REPEAT_PROBE` | bool | 0 | subproblem_invocation_counter.py | P1 #12 cache-trio spike 探针, 收集 subproblem repeat rate |
| `EXACT_SUBPROBLEM_REPEAT_LOG_DIR` | path | data/telemetry | subproblem_invocation_counter.py | subproblem repeat probe 日志目录 |

---

## I. Power coverage 编码变体 (P0 #1 follow-up)

各种 power coverage witness encoding 实验. 实际生产用 default.

| Name | Type | Default | Reader | 作用 |
|---|---|---|---|---|
| `EXACT_POWER_COVERAGE_WITNESS_ENCODING` | str | (内部) | exact_coordinate_master.py | witness encoding 选择 |
| `EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY` | str | (内部) | exact_coordinate_master.py | witness block geometry |
| `EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE` | int | (内部) | exact_coordinate_master.py | witness block size |
| `EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING` | str | (内部) | exact_coordinate_master.py | selected interval encoding |
| `EXACT_POWER_FAMILY_LOOKUP_ENCODING` | str | (内部) | exact_coordinate_master.py | family lookup encoding |
| `EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING` | str | (内部) | exact_coordinate_master.py | shell distance encoding |

---

## J. Process priority / 系统

| Name | Type | Default | Reader | 作用 |
|---|---|---|---|---|
| `EXACT_PROCESS_PRIORITY` | str (normal/high) | normal | runtime/process_priority.py | Windows process priority override |

---

## K. Phase 3B specific

| Name | Type | Default | Reader | 作用 |
|---|---|---|---|---|
| `PHASE3B_ANCHOR119_ADVISORY` | bool | 0 | phase3b anchor119 *.py | anchor119 advisory 启用 |
| `PHASE3B_DIRECT_EQUALITY_CORE_EXCHANGE_SOURCE` | path | (内部) | phase3b_coordinate_validation_direct_equality_core.py | direct equality core source |
| `PHASE3B_DIRECT_EQUALITY_CORE_GEOMETRY_SOURCE` | path | (内部) | phase3b_coordinate_validation_direct_equality_core.py | direct equality core geometry source |
| `PHASE3B_FULL_FORCED_HINT_FIELD_FAMILY_DELTA_SOURCE` | path | (内部) | phase3b_full_forced_hint_field_family_delta.py | full forced hint field family delta source |
| `PHASE3B_SAME_X_CAPACITY_ANCHOR_SWEEP_SOURCE` | path | (内部) | phase3b same X capacity anchor sweep | same X capacity sweep source |

---

## 注意事项

### Pre-commit gate 自动 strip 的 runtime env

`scripts/preflight_gate.py` 在跑 pytest 前会自动剥离这 4 个 env (防污染单元测试):
- `EXACT_OUTER_SKIP_UNKNOWN`
- `EXACT_BINDING_DUMP_STATE`
- `EXACT_MASTER_HINT_PERSISTENCE`
- `EXACT_BINDING_USE_OVERLOAD_SEPARATION`

**新加 runtime-only env 应该同步加进这个 strip list**, 否则 pre-commit 跑测可能被开发环境污染.

### Production wrapper 默认设置

`scripts/run_campaign_p2_workers1.sh` (推荐启 168h 用) 默认 export:
- `EXACT_MASTER_CP_SAT_WORKERS=1`
- `EXACT_GATE_WORKER_PEAK_RSS_GIB=14`
- `EXACT_OUTER_SKIP_UNKNOWN=1`
- `EXACT_COMMUNITY_BLUEPRINT_HINT_PATH=data/hints/blueprint_2026_05_13_master_hint.json`

`scripts/run_campaign_workers2.sh` (fallback) 默认:
- `EXACT_MASTER_CP_SAT_WORKERS=2`
- `EXACT_GATE_WORKER_PEAK_RSS_GIB=20.5`
- `EXACT_OUTER_SKIP_UNKNOWN=1`
- `EXACT_COMMUNITY_BLUEPRINT_HINT_PATH=...`

### 命名约定

- `_ENV` 后缀: 源码里 `_XXX_ENV = "EXACT_..."` 这种是 **Python 常量名**, 实际 env 名是它指向的字符串. 文档列后者.
- `_FALSE_VALUES` / `_TRUE_VALUES` 后缀: 是值解析辅助常量, 不是真 env. 不在此列.
- `_FINAL_TARGET` / `_SELECTED_BLOCK` 等子选项: 是 multi-stage 编码内部子值, 不在此列, 见 exact_coordinate_master.py 内部.

---

## 如何添加新 env

1. 在源码里 `os.environ.get("EXACT_FOO_BAR", default)` 或者定义模块常量 `_FOO_BAR_ENV = "EXACT_FOO_BAR"` 然后 `os.environ.get(_FOO_BAR_ENV, ...)`
2. 在本文档对应分组里加一行
3. 如果是 runtime-only (生产 wrapper 用, 单元测试不该受影响), 加进 `scripts/preflight_gate.py` 的 strip list
4. 如果 production critical, 在 wrapper (`scripts/run_campaign_p2_workers1.sh` 等) 给 sensible default

---

## Memory 链

- [[project_d_step2_hint_landed]] — EXACT_COMMUNITY_BLUEPRINT_HINT_PATH 落地详细
- [[project_30gb_real_culprit_power_coverage]] — EXACT_MASTER_CP_SAT_WORKERS 调研背景
- [[project_p1_24_oom_blocked]] — EXACT_GATE_WORKER_PEAK_RSS_GIB OOM headroom 公式背景
