# Shared Infrastructure (跨 lever 共享 production code)

## 目的

24 lever 的 production-level 实施代码不少在 `src/` 内主仓共享 (例如 `pose_bool_exact_master.py` 既 B1 paradigm 实施又 path 12-17 + L23 都共用). 跨 lever 共享的 production code 放这里, 不在每 lever 文件夹复制.

## 包含

### src/models/
- **`pose_bool_exact_master.py`** (1000 LOC) — B1 paradigm core + path 12-17 + L23 augmented 全用. env `EXACT_USE_POSE_BOOL_MASTER=1` 启用. 含 `add_routing_port_blocking_cell_cut` / `add_benders_cut` / `add_patch_routing_core_cut` / `add_separator_capacity_cut` / `add_routing_port_lazy_demand_cut` 等所有 cut form 实施
- **`master_model.py`** (11K+ LOC) — `MasterPlacementModel` 总入口, `build_exact_core` / `from_exact_core` / `solve`. 含 `PoseBoolExactMasterDelegate` 跟 `CoordinateExactMasterDelegate` 切换 (env 控制)
- **`exact_coordinate_master.py`** — coordinate master 实施 (L1-L10 era 主线, 后被 B1 pose-bool 替换)
- **`binding_subproblem.py`** — port binding LBBD sub-problem. RAB-SEP 加 filter, Path 12 实施
- **`routing_subproblem.py`** — routing belt CP-SAT, 含 routing precheck `front_blocked` detect
- **`d2_commodity_flow_core.py`** (281 LOC) — Path 17 D2 sub-problem core class
- **`separator_capacity_hull.py`** — Path 13 SAC-Hull 实施
- **`abstract_routing_layer.py`** — Path 13 L2 abstract routing layer
- **`patch_routing_core.py`** (983 LOC) — Path 14 PCR-CUT 实施
- **`routing_binding_context.py`** — Path 12 RAB-SEP 实施

### src/search/
- **`benders_loop.py`** (3K+ LOC) — outer LBBD search loop, `run_benders_for_ghost_rect` + `create_exact_search_session`. 所有 paradigm env-gated hook 都在这 (`EXACT_USE_POSE_BOOL_MASTER` / `EXACT_B1_*` / `EXACT_B1_D2_COMMODITY_FLOW` / 等)
- **`d2_separator.py`** (215 LOC) — Path 17 D2 sub-problem separator orchestrator
- (其他 separator: `patch_conflict_separator.py` Path 14 / `separator_capacity_separator.py` Path 13 也在 src/search/ 但未 copy 进此包)

## 项目根

- **`PROJECT_LOCK.md`** — 项目硬约束 (certified_exact 严格分离, 不准 master 内 pose 预筛, AI sidecar 安全合同)
- **`CLAUDE.md`** — 项目 instructions 给 Claude (工具/约束/conventions)
- **`docs/lever_verdicts.md`** — 24 lever 完整 verdict source of truth

## 怎么读

每 dead_paths/{lever}/README.md 引用此处文件时给的 path 是 `shared_infra/src/models/foo.py`. 你可以**只读这些文件相关部分** (e.g. 看 path 14 PCR-CUT, 主要看 `shared_infra/src/models/patch_routing_core.py` + path14_pcr_cut/code/ 内 trial scripts).

不必读完整 src/. 但**核心 4 个 file** 是: `master_model.py` + `pose_bool_exact_master.py` + `benders_loop.py` + `binding_subproblem.py`. 这 4 个 file 是 24 lever 框架基石.

## full_source.tar.xz — 完整源码 (2.1 MB)

`shared_infra/full_source.tar.xz` 含整个项目 source code (除 __pycache__ / .pyc / .git / .venv / data 大文件 / artifacts):

- `src/` — 全部 Python 源码 (716 .py file, models / search / preprocess / runtime / adapters / render / placement / io / interchange / ai_accel / rules / tests)
- `paths/` — paradigm investigation trial scripts (15-17)
- `rules/canonical_rules.json` — 项目源 truth (consolidated preprocess/recipe/target/commodity)
- `specs/` — schema 定义
- `data/preprocessed/` — candidate_placements / mandatory_exact_instances / generic_io_requirements 等源 truth artifacts
- `main.py` — entry point
- `PROJECT_LOCK.md` / `CLAUDE.md` / `README.md` / `FILE_STATUS.md` / `CHANGELOG.md` / `BORROWED_COMPONENTS.md` — 顶层文档
- `docs/lever_verdicts.md` — 24 lever 源 truth
- `requirements.txt` — Python deps

解压:
```bash
tar -xJf full_source.tar.xz
```

总 ~14 MB uncompressed, 927 files. 跟之前 v7/v9 包 code.tar.xz 同 convention.

shared_infra/src/ 内的 5 个 file (master_model / pose_bool_exact_master / binding_subproblem / routing_subproblem / exact_coordinate_master / benders_loop) 跟 tarball 内 src/ **重复**, 留作 quick reference (GPT 不必解 tar 也能直接看核心 4 file).
