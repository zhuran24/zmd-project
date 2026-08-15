# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

《明日方舟：终末地》70×70 基地的 **certified-exact 最大空矩形求解器**（Python 3.13 + OR-Tools CP-SAT）。
入口 `main.py`，默认 `--mode certified_exact`。

---

## 0. 权威顺序、知识入口与文档自举（先读这条）

### 文档操作先查询目标契约

新建、编辑、移动或删除 Markdown、`DOC_POLICY.json`、知识账本或文档框架文件前，先运行：

```bash
.venv/bin/python devtools/docctl.py context <path> --intent <read|edit|create|move|delete>
```

按操作卡给出的 mutation、短原因、write-through 源、required reads 和 after-change 命令执行；完成后运行：

```bash
.venv/bin/python devtools/docctl.py check --changed
```

唯一固定自举入口是 `.docsystem/manifest.json`。普通文件只加载当前路径需要的短卡；命中 policy、schema、resolver、框架指南等 framework core 时，`docctl` 会自动提升到 L2/L3，并给出完整架构、维护协议和 ADR 坐标。若 resolver 无法启动，按 `.docsystem/RECOVERY.md` 恢复。不要凭文件名或旧经验猜维护方式。

### 项目 authority 与知识入口

不同源管辖不同问题，不再用一张手写状态页覆盖所有问题：

1. `PROJECT_LOCK.md` 管 certified exactness、命题 P、Accepted Invariants、Forbidden Changes 与发布边界。
2. `rules/canonical_rules.json` 管 canonical 游戏规则；`data/proof_obligations/` 管机器义务；`data/review_gates/` 管 owner-only phase gate；对应问题发生冲突时回到各自机器源。
3. `docs/CURRENT.md` 是从机器源和稳定账本生成的唯一人类可读现态投影。它便于查询，但不高于源文件，禁止手工修改。
4. `docs/START_HERE.md` 按任务导航；`docs/CATALOG.md` 查稳定 claim、decision、dossier 与 review；`docs/REASONING_LEDGER.md` 查推理分类；`docs/VALIDITY_LEDGER.md` 查反例、失效、修复、复用与显式换代；`docs/BACKFILL_LEDGER.md` 区分 semantic review 与 inventory triage；`docs/TOPIC_INDEX.md` 和 `docs/TERMINOLOGY.md` 提供主题与术语入口；`NAV_MAP.md` 查代码和数据入口。
5. `docs/项目说明/ROADMAP.md` 只承担未来工作，`docs/项目说明/HISTORY.md` 只追加带日期的编年史，`docs/项目说明/REASONING_METHOD.md` 保存稳定方法；`docs/research/**` 是证据档案。它们都不能覆盖 CURRENT 引用的机器 authority。当前哪些文档仍承担职责，以生成的 `docs/GUIDANCE_INDEX.md` 为准。

根 `README.md` 只做仓库前门，不再复制 gate、阶段、研究 U/L 或开关状态。旧的 `FILE_STATUS.md`、`06_current_status.md` 与 `27_status_dashboard.md` 已降为兼容入口，其历史正文保存在 `docs/history/status/`。

**绝不能从绿灯推导关门。** checker PASS、preflight 全绿、测试全过、`supervisor_seal()` 方法存在
——都只说明「登记结构未漂移」，不构成 soundness 证明、不构成 owner 关门动作、不构成 release closure。

---

## 1. 解释器：必须用 `.venv/bin/python`

系统 python 没有 `ortools` / `mypy` / `ruff` 等，`main.py` 直接 `ModuleNotFoundError`。
preflight 的 `[0/18] 解释器自检` 会 fail-closed 并停掉后续所有 lane（判据是**能力而非身份**：
Python ≥ 3.13 且 `jsonschema / mypy / ortools / pytest / ruff / yaml` 全可导入）。

更该防的是反面：**装了部分依赖的解释器会让门禁跑完并报绿，但检查面根本不是项目要求的那一套**。
本文档所有 `python` 一律指 `.venv/bin/python`。

依赖锁在 `requirements.lock.txt`（运行时）+ `requirements-dev.lock.txt`（mypy/ruff/pytest-randomly）。
项目没有 `pyproject.toml`，配置分散在 `ruff.toml` / `pytest.ini`。

---

## 2. 常用命令

### 门禁（唯一权威验收面，`scripts/preflight_gate.py`）

```bash
.venv/bin/python scripts/preflight_gate.py              # staged 范围快检
.venv/bin/python scripts/preflight_gate.py --full       # 全量：19 道 gate + 全部 pytest（仍 -m "not slow"）
.venv/bin/python scripts/preflight_gate.py --slow-tests # 专用慢 soundness lane（-m slow，串行，2400s 超时）
.venv/bin/python scripts/preflight_gate.py --ci --base-ref origin/main   # 按 diff 范围
```

`--full` 依次跑：解释器自检 → 冻结/外部工件 hash → 禁提交路径 → `src/ai_accel` 安全契约 →
精确/探索隔离 → 研究审计覆盖 → 行尾 → secret 扫描 → artifact 边界 → phase gate →
P1.2 义务 → strong-status allowlist → mypy → ruff → pytest → 记忆 lane。

### 测试

```bash
# 单文件 / 单 nodeid 的标准形态（-p no:randomly 固定顺序，独立 basetemp 防互删）
.venv/bin/python -m pytest -p no:randomly --basetemp=.pytest_tmp/one -q src/tests/test_exact_contract.py
.venv/bin/python -m pytest -p no:randomly --basetemp=.pytest_tmp/one -q \
    "src/tests/test_exact_contract.py::test_exact_mode_uses_flow_only_as_diagnostic"

# 快 lane 手动重现（跨核并行）
.venv/bin/python -m pytest -q -m "not slow" -n auto src/tests/
```

`pytest.ini`：`testpaths = src/tests`、`--basetemp=.pytest_tmp`、marker `slow` / `evidence` / `replay`。

### 单点 checker（比跑全量快，定位 drift 用）

```bash
.venv/bin/python scripts/check_p1_2_proof_obligations.py        # close-kernel 结构 + V99 source-sha
.venv/bin/python scripts/check_strong_status_write_allowlist.py # strong-status 写点 deny-by-default 清单
.venv/bin/python scripts/check_phase_review_gate.py             # owner phase gate 形态
.venv/bin/python scripts/check_external_artifacts.py --require candidate_placements
.venv/bin/python scripts/check_line_endings.py
.venv/bin/python devtools/check_repository_code_assets.py check # 代码资产分类/投影
.venv/bin/python devtools/docctl.py context <path> --intent edit  # 当前路径的文档操作卡
.venv/bin/python devtools/docctl.py check --changed              # 本次文档/框架 diff 闭环
.venv/bin/python devtools/docctl.py doctor                       # 文档框架、自举与兼容投影
.venv/bin/python devtools/build_knowledge_docs.py --refresh-dossiers --write # 更新八份知识投影
.venv/bin/python devtools/check_knowledge_docs.py                 # 知识账本、前门与生成投影
```

### lint / 类型

```bash
.venv/bin/python -m ruff check .        # 全仓，任何 warning 都 BLOCK（噪音已由 ruff.toml 吸收）
.venv/bin/python -m ruff check <file>   # 改 pin 文件前先把它弄全绿（见 §6 步 2）
.venv/bin/python -m mypy --explicit-package-bases --ignore-missing-imports --follow-imports=silent <targets>
```

mypy 只 strict 到 `MYPY_STRICT_TARGETS`（`scripts/preflight_gate.py` 内）：cut lifecycle 核心 +
`master_model.py` / `benders_loop.py` + Stage B typed TCB 文件。

### 求解 / 发布

```bash
.venv/bin/python main.py --mode certified_exact --campaign-hours 8      # 只会停在 CANDIDATE_PROPOSED
.venv/bin/python main.py --mode exploratory                             # 启发式/诊断，永不能升为证明
.venv/bin/python scripts/run_supervisor_seal.py                          # 唯一 durable CERTIFIED mint 的生产入口
bash scripts/run_campaign_linux.sh                                       # wrapper，自动注入 --resume-campaign
```

### 恢复外部大工件

`data/preprocessed/candidate_placements.json`（54,467,709 bytes）在轻量副本里可能缺失：

```bash
.venv/bin/python scripts/check_external_artifacts.py --require candidate_placements
.venv/bin/python scripts/restore_external_artifacts.py candidate_placements --source <file> --force
```

---

## 3. 命令坑节

- **preflight 退出码只有 0/1**（`GateResult.exit_code`）。没有返回 2 的路径，别写 `if code == 2`。
  判 BLOCK 看 blockers 非空或输出里的 `BLOCK` 行。
- **`--full` 不是全部测试**：它固定追加 `-m "not slow"`。改认证核心（producer / seal / publish /
  checker / V99 钉死的源文件）后**必须另跑 `--slow-tests`**，否则慢 soundness 是盲区。
- **`@slow` 是集中登记不是散落装饰器**：名单在 `src/tests/conftest.py::_SLOW_TEST_NODEIDS`（字面 nodeid 的
  frozenset）。新写 ≥8s 的测试要去登记，否则会被快 lane 跑到、把秒级门拖成分钟级。
  「登记条数」与「`-m slow` 收集到的实例数」是两个口径（参数化会放大），别混用。
- **并发跑 pytest 会互删临时目录**：`--basetemp=.pytest_tmp` 是全局的，两个 pytest 进程共用并清理同一
  basetemp。多窗口时每个进程显式覆盖 `--basetemp=.pytest_tmp/<独立子目录>`。
- **测试顺序不稳定**：`pytest-randomly` 装了就随机排序、没装就自然序，同一条命令在两台机器上顺序不同。
  要可复现永远显式带 `-p no:randomly`。
- **缺 `candidate_placements.json` 是硬失败不是优雅 skip**：`test_binding.py` / `test_routing.py` 的若干
  用例在 fixture 阶段直接读它，缺失时抛 `FileNotFoundError` 变成一批 error。看到「一批测试莫名 error」
  先跑 `check_external_artifacts.py --require candidate_placements`。
- **静默 skip 比红更危险**：验收要看 skip 数字而不只看 passed；外部依赖不可避免时用 `pytest.fail` 而不是
  `skip`。判据不是「skip 多不多」，是「它在别处有没有被验证」。
- **认证链测试在跑时整棵树必须冻结**：认证链校验是字节级的、且在生产 runtime 路径上。慢 lane / preflight
  的 pytest 段运行期间，任何 `src/` `scripts/` 改动——包括纯新增函数、只改 docstring、非 sealed 文件、
  一次 `git commit`——都会让 source digest 中途变化，跑成假红。source digest 范围**大于** sealed 名单。
  长门禁发射前先把要提交的提交完，跑起来后只做树外工作。看到认证链测试莫名红先 `git status`。
- **`--exploratory` 会覆盖 `--mode`**；`--skip-readiness-gate` 只跳启动门、不跳 freeze monitor。
  另外 exploratory 在 prod-scale 上不可用（port clearance 启发式 build 爆炸）。
- **`scripts/production_readiness_gate.py` 不是纯只读**：它面向 CachyOS/pacman 写、会 `mkdir .artifacts`，
  别在只读勘察流程里顺手跑。
- **`scripts/select_tests_for_paths.py` 的 exit 2 = 「建议跑全量」**，不是精确受影响闭包。
- **跑完 `main.py` 只会得到 `CANDIDATE_PROPOSED`**，这是刻意留开的操作链缺口不是 bug（见 §4.3）。
- **门禁/测试命令永远 `> log 2>&1` 全量落文件**，别 `| tail`：管道裁掉失败细节，且退出码被 `tail` 顶成 0。
- 后台长命令的 timeout 被 clamp 到 600s。>10min 的活写成脚本用 `setsid nohup script.sh &` 跑，
  末尾 `touch <名>.DONE` 并把退出码写进日志，用标记文件判终态（**别用日志哨兵、别用 `pgrep -f`**——
  `-f` 匹配整条 argv，监控脚本会匹配到自己）。

---

## 4. 大图

### §1 问题与目标

当前认证问题面的机器值统一从 [`docs/CURRENT.md`](docs/CURRENT.md) 读取，包括 active base、
网格、mandatory 实例数、目标、最短边 admissibility 与空矩形语义。不要把这些值复制到新的操作文档。

下面是不会因一次状态更新而改变的解释边界：

- `min_side` 是候选 admissibility 与 lex 目标的第二坐标，精确定义来自 canonical rules 和命题 P。
- `Phi(w, h)`、`(area, width, height)` 或任何启发式评分都不是 exact 比较器。
- exploratory cap、hint、probe 与 sidecar 不能进入 certified 证明链。
- 供电覆盖、端口 exact-count、离散路由连通和物料吞吐是不同谓词，不能压成一句“资源够”。
- active scope 之外的基地默认是 future scope，当前结论不得自动外推。

### §2 唯一最重要的规则：`certified_exact` vs `exploratory`

两条严格隔离、永不交叉的求解路径：

| 路径 | 可以 | 绝不可以 |
|---|---|---|
| `certified_exact`（默认） | 产 proof-relevant 候选材料；binding/routing gate；fixed-witness 复验；supervisor seal；已验证发布 | 拿 exploratory cap/hint/probe/sidecar 当证明；让诊断 flow 门控；绕过冻结工件/hash/owner gate |
| `exploratory` | 启发式、诊断、可视化、sidecar、性能探针、经验 cap | 产 certified 剪枝证明、terminal `CERTIFIED`、public certified 交付 |

三条被记为 Forbidden Change 的否决方案：① 把 exploratory cap/hint 当精确上下界（hint 只允许写 CP-SAT
`solution_hint` proto，永不写约束）；② 让 flow 模型门控剪枝/发布（`flow_subproblem.py` 是连续 LP/GLOP，
**diagnostic-only、永不 gate**，有契约测试 monkeypatch flow→INFEASIBLE 仍断言 CERTIFIED）；
③ 让 postprocess/serializer/viewer/adapter 成为发布权威。

preflight 有一道 `EXPLORATORY_LEAK_PATTERNS` diff 扫描，专盯 `EXACT_MODE_FILES` 那 6 个核心文件。

### §3 producer / supervisor / publisher 三分（PR1）

证明权威被刻意拆开，任何单一写方都铸不出 public `CERTIFIED`：

```
main.py → run_solve() → src/search/outer_search.py
  PRODUCER（F-CAM-PR1-01）：跑搜索，terminal 只提交 CANDIDATE_PROPOSED + 证据材料。
                            任何 producer 侧 mark_campaign_stopped(..., "CERTIFIED") 被拒。
    └ src/search/benders_loop.py                Benders / LBBD 主循环
       ├ src/models/exact_coordinate_master.py  默认 certified placement master (CP-SAT)
       ├ src/models/pose_bool_exact_master.py   env-gated 备选 master；certified 下显式禁用，不是 public backend
       ├ src/models/binding_subproblem.py       CERTIFIED GATE：端口绑定 + exact-count
       ├ src/models/routing_subproblem.py       CERTIFIED GATE：栅格路由（连通，不是吞吐）
       ├ src/models/flow_subproblem.py          DIAGNOSTIC ONLY —— 永不 gate
       ├ src/search/independent_infeasibility_reverifier.py  whole-layout nogood 落 cut 前独立复验
       └ src/cuts/lifecycle.py                  cut 生命周期；certified attach 须经 authority gate（当前状态见 CURRENT）

scripts/run_supervisor_seal.py  →  ExactCampaign.supervisor_seal()
  SUPERVISOR MINT（F-CAM-PR1-02）：唯一 durable terminal CERTIFIED mint。
  从**磁盘**读已提交提案，复验 proposal + campaign 绑定，跑 sink replay 与 fixed-witness 复验，
  写前写后各验一次磁盘状态。caller 手里的内存映射不是权威。

publish_verified_certified_delivery_surface()   （src/search/certified_surface.py）
  PUBLISHER（F-CAM-PR1-03）：唯一 public certified 发布器。要求 sealed + disk-current +
  terminal-frontier-evidence + open-gate-passed，然后在**同一个事务**里派生
  data/solutions/final_solution.json、data/blueprints/optimal_blueprint.json、
  data/solutions/certified_delivery_manifest.json，写后复验，失败清理半成品。
  （F-CAM-PR1-04）内部 seal 有效是**必要非充分**——P1.2 owner gate 必须独立解析为显式 closed 形态。
```

**方法存在 ≠ 入口存在 ≠ release closure。** `main.py` 至今停在 `CANDIDATE_PROPOSED`。

### §4 命题 P：CERTIFIED 证什么、不证什么

**证（6 条 gating 谓词，任一 INFEASIBLE 都阻止 CERTIFIED）+ lex 最优性：**

1. ghost 矩形内无 facility（ghost optional interval 并入同一组 `AddNoOverlap2D`）
2. instance 两两不重叠
3. per-instance `placement_rule`（生成期 fail-closed 硬绑 + master 域限制，双闸）
4. 端口绑定可行，含**端口级 exact-count**（0/1 计数等式；**不证每口离散吞吐速率**）
5. 路由可行 = **离散有向连通**（source front → sink front 可达，全局复验拒 local-only incumbent）
   + 所有 route cell 落在空矩形之外。`capacity` 那条 `AddAtMostOne` 只是「一格一层至多一条 route-state」
   的静态空间互斥，**无时序维度、不是吞吐容量**
6. 供电覆盖可行（最强谓词）：master 硬约束「塔覆盖矩形与受电 footprint **相交** ≥1 格」（不是包含），
   **外加一道独立 terminal 复验**从冻结工件原始 pose 字节逐格重算覆盖 + 无冗余塔检查，不信 solver 内部变量

**不证（冒充即触发 Forbidden Change）：**

- 物料离散吞吐 / 传送带带宽容量（谓词 5 只到连通；唯一带 demand 量纲的 flow 子问题被锁成 diagnostic-only）
- ~98% 密度下的容量/连通（open research problem。active cut family F1-F7+F9 是**面积/空间密度 packing cut，
  不是吞吐 cut**；进 certified 需要新范式，不是「关现有 gap」）
- 「资源够」的三种精度不得混成一句：① 端口级 exact-count = 已 certified；② 电力**覆盖**充分性 = 已
  certified（**非**电力吞吐配平）；③ 物料离散吞吐充分性 = **未 certified**
- 机器间物理间隙不是 P 的谓词（`machine_min_clearance_cells=1` 管的是端口 connector 格必须空，
  不是机身间距；机身贴着是合法的）

**几何信任边界（命名 TCB）**：solve 期只有两件几何事实被独立重导——实心 footprint 的
`occupied_cells == bbox`，以及供电桩 radius-5 / 2×2 诱导的 12×12 方形覆盖。冻结
`candidate_placements.json` 里其余 pose 字节（`occupied_cells` / `power_coverage_cells` / 端口坐标）
**是被采信的命名 TCB**，靠生成期 `placement_generator._validate_template_geometry_contract` fail-closed
+ artifact hash-pin 兜底。canonical 规则 → 几何字节的映射是 owner 确认的规格事实，不是代码自动证明的定理。

### §5 目录职责

| 目录 | 角色 |
|---|---|
| `src/search/` | outer producer、campaign、frontier、fixed-witness、supervisor seal、中央发布面 |
| `src/models/` | master / binding / routing；flow 仅诊断 |
| `src/cuts/` | cut 生成、独立校验、typed lowering 与生命周期；当前 family 状态见 `docs/CURRENT.md` |
| `src/io/` | strict JSON、序列化、delivery manifest；**不单独拥有发布权** |
| `src/render/`, `src/adapters/` | postprocess/交付面，必须消费中央验证后的 authority |
| `src/ai_accel/` | AI 加速面；preflight 逐行扫描、禁止出现 `data/checkpoints` / `data/solutions` / `data/blueprints` 字样 |
| `src/tests/` | 单元 / 回归 / soundness 红测；根目录 `test_*.py` + `cuts/` + `phase3b/` |
| `rules/`, `data/preprocessed/` | canonical rules 与冻结输入 |
| `data/proof_obligations/` | P1.2 机器义务、sink inventory、allowlist |
| `data/review_gates/` | owner 手动 phase gate |
| `data/knowledge/` | claim、decision 与 dossier 的结构化账本；不能越权覆盖 evidence source |
| `docs/CURRENT.md`, `docs/CATALOG.md`, `docs/REASONING_LEDGER.md`, `docs/VALIDITY_LEDGER.md` | 自动生成的当前状态、知识目录、推理回填与有效性换代投影；禁止手工编辑 |
| `docs/history/` | 被替换入口与状态页快照，只作历史追溯 |
| `devtools/` | 仓库治理与研究运行契约（非 certified TCB） |
| `.artifacts/`, `docs/research/` | 一次性评审证据与历史研究档案，**不是活代码**（ruff 已 exclude） |

### §6 cut framework 的操作边界

当前 family 状态、attach 开关边界与 B6 决定从 `docs/CURRENT.md` 中的
`CLAIM-CUT-FRAMEWORK-PRODUCTION-STATUS` 和相应 decision 读取，不在本文件复制一张状态表。

操作上始终遵守三条：typed registry 不等于 production admission；shadow 结果不得改写 master；
任何 certified attach 或默认值变化都必须经过 `PROJECT_LOCK.md` 规定的 production integration 与 owner gate。
Feature toggle 一律走已登记的 `EXACT_*` 环境变量，配置入口见
`docs/项目说明/18_workflow_env_config.md`；不得用临时环境覆盖绕过 certified unsafe map。

---

## 5. Frozen artifacts 节

字节级钉死的输入（清单权威 = `scripts/preflight_gate.py` 的 `FROZEN_ARTIFACTS` /
`EXTERNAL_FROZEN_ARTIFACTS`；runtime 侧另有 `src/search/certified_artifact_contract.py` 的源码常量）：

- `rules/canonical_rules.json`
- `rules/preprocess_plan.json`
- `data/preprocessed/mandatory_exact_instances.json`
- `data/preprocessed/generic_io_requirements.json`
- `data/preprocessed/candidate_placements.json`（外部大工件，轻量副本可缺；certified 跑之前必须恢复同一字节）

> 本文件**刻意不抄任何 sha / 字节数**——抄一份就是再造一处必须随 reseal 维护的 pin 面。
> 需要真值时从上面两个源码位置取，或 `git show HEAD:<file> | sha256sum`。

**mismatch 时绝不「好心」更新 expected 值。** pin 是身份声明，不是当前文件的校验和。历史上有多代
hash-incompatible 的 `candidate_placements.json`（`a914…` / `adcc…` / `d5e3…` / `78e2…`），它们**必须**
被 `artifact_hash_mismatch` 拒绝。看到 mismatch 先查「是文件错了还是 pin 该动」；
只有确实换代的批才走 freeze-ritual，**单改一个 expected 常量永远是错的**。

---

## 6. freeze-ritual 节（改任何被字节级钉死的文件）

适用面：上节 5 个冻结工件 + close-kernel V99 名单里的源文件 + `PROJECT_LOCK.md` + `scripts/preflight_gate.py`。
完整版见 `docs/项目说明/28_pitfalls_and_sop.md` SOP-1/SOP-2。

1. **判定 pin 面**：`git grep` 起手搜**旧值本身**（不是常量名——常量名在各处不统一，按名字搜必漏），
   大小写不敏感（`-i`：有的站点是大写 sha）。分三堆记账：活代码/测试 pin、文档展示 pin、
   **史料门/replay 门（故意留旧值，不改）**。判据是「这个 pin 会不会在门跑起来时被真比对」——
   靠**跑一次目标测试文件**定，不靠是否被 import。
2. **先清 ruff**：要改的源文件先 `ruff check <file>` 全绿。reseal 途中被 ruff 逼着二次改码 → sha 又变 →
   前面填好的 pin 全部失效。
3. **改字节**：tracked 文件一律用 Edit 工具改（保持原行尾）。**绝不 `write_text` / `json.dump`**——
   `.gitattributes` 强制 LF，Python 文本写入在 Windows 侧写 CRLF，本地读磁盘的门能过、CI 读已提交树挂。
4. **重生成派生产物**，或机器验证「派生字节不变」并留验证输出（别口头断言）。
5. **更新 pin 走迭代法**：填一处 → 重跑 checker → 它精确报下一处 drift → 再填，直到 PASS。
6. **跑全套门**：两个结构 checker + `--full` + `--slow-tests`。慢 lane 不能省。
7. **提交**：pathspec = 完整一致集；push 前 `git show HEAD:<file>` 核对钉死表期望值。

**四条 reseal 连锁**（判定入口：你改的字节被谁钉着）：

- **链 A 冻结工件字节变** → `preflight_gate.py` 的两张表（大写 sha）→ `certified_artifact_contract.py`
  源码常量（小写）→ 各处文档展示 pin → `docs/research/` 下的**活契约**文件（被 `.rgignore` 藏起来，
  必须 `git grep` 才看得见）。
- **链 B V99 钉死的源文件字节变**（按序）→ ① `check_p1_2_proof_obligations.py` 的
  `CLOSE_KERNEL_V99_REQUIRED_SOURCE_SHA256_BY_PATH`（同一个 dict 兼任 registered sink pin 与 v99 sealed
  floor 两职）→ ② `data/proof_obligations/p1_2_proof_obligations.json` 里该 entry 的 `source_sha256` →
  ③ checker 自身字节因步 ① 变了，更新它在**同一个 JSON** 里的 self-pin。
  **self-pin 在 JSON 不在源码，所以没有鸡生蛋；最后算、最后填。**
- **链 C `scripts/preflight_gate.py` 字节变** → `src/tests/cuts/test_rule_cut_evolution_authority_parity.py`
  的 `_PROTECTED_SURFACE_SHA256`（successor 注释记代保留，别抹掉上一代）。
- **链 D `PROJECT_LOCK.md` 字节变 = 6 + 1**：3 处测试 pin（parity 测试的 `_PROJECT_LOCK_SHA256`、
  `test_w0_d6_gate.py` 的 `PROJECT_LOCK_SHA256`、`test_w0_d6_replay.py` 的 `EXPECTED_PROJECT_LOCK_SHA256`）
  + 3 个 D6 研究脚本常量（**名字不统一**）+ 1 个派生环（antecedent 内嵌 lock sha，要用 gate 模块**重建重算**
  不能手填）。改完三个测试文件全绿再提交。

同型清单不止文件 sha：canonical sha、**解释器路径**（验证器与 fixture 钉死了 venv 路径）、
外部根路径常量——**修任何环境身份之前先 `git grep` 老身份字符串找 pin 面**。

---

## 7. 禁提交路径节

求解产物不进 git（`scripts/preflight_gate.py::FORBIDDEN_STAGED_PATHS`）：

```
data/checkpoints/
data/blueprints/optimal_blueprint.json
data/solutions/final_solution.json
data/solutions/certified_delivery_manifest.json
```

注意 **`data/solutions/` 不是整目录忽略**——`.gitignore` 走精确路径，该目录下其余审计文件正常跟踪。
别为了省事把整个目录加进 ignore。另外 `src/ai_accel/**/*.py` 里不得出现 `data/checkpoints` /
`data/solutions` / `data/blueprints` 字样（preflight `check_ai_safety_contract` 逐行扫描，注释行豁免）。

本仓常有并发会话共用同一工作区和同一个 `.git/index`：

- **裸 `git commit -m` 会把别人 staged 的文件一起提交**。提交前重看 `git status --short` 与
  `git diff --cached --name-only`，只用带明确 pathspec 的提交命令，pathspec 要精确等于这次逻辑改动的
  完整一致集（漏了 pin 引用的文件 → 本地读磁盘能过、CI 读已提交树才炸）。
- **`--amend` 改的是 HEAD，而 HEAD 可能已被别的会话推进过**。amend 前先 `git log --oneline -1` 比对
  **hash**（不是比对 message）。误 amend 的无损修法：`git reset <对方原提交hash>` 走 mixed 模式
  （**别 `--hard`**），再用精确 pathspec 单独提交。
- **共享工作区里的 untracked 文件会消失**（并发会话的清理动作会带走）。真正的安全线是「进了 commit」：
  产物写完立刻 `git add` + 精确 pathspec 提交，把窗口压到秒级。
- `scripts/package_review_snapshot.py` 打的是**已提交树**，不含脏改动。给外审打包前先提交。

本地没有安装 git hook（`.githooks/` 不存在，`scripts/install_hooks.py` 当前无源可装），
门禁靠手动跑 `preflight_gate.py`。

---

## 8. 读代码的工具约定节

```bash
rg -n '<keyword>'                    # 开发者视角，遵守 .rgignore 投影
git grep -n -I -e '<keyword>' --     # 全部 tracked 路径，忽略 .rgignore
```

**承重结论一律 `git grep` 起手。** 默认参数下的一次 `rg` 给的是被裁剪过的投影，
「搜不到 = 不存在」在这个仓库不成立，有三种系统性漏报：

1. **`.rgignore` 投影**把 `docs/research/**/*.py|.pyi|.sh|.ps1` 整类排出 rg 默认结果，
   而那片里混着被 `src/tests/` 真导入执行的**活契约**文件；
2. **pin 值在源码里可能是相邻字符串拼接**写的（运行时是完整名，grep 完整字面量零命中）；
3. **同一个 sha 在不同文件里大小写不同**（一处大写常量、一处小写），大小写敏感的 grep 会漏。

非要用 rg 就带 `--no-ignore --hidden`，并排除 `.git/` `.artifacts/` `.pytest_tmp/` `.claude/worktrees/`
（最后一条是别的会话的副本，命中了也不能改）。查集合成员资格用 python import 把集合 print 出来，
或跑对应契约测试，别只 grep 字面量。

`.rgignore` 只是开发者搜索投影：它隐藏历史源码与 retirement candidate，**不隐藏**现行 specs、
`PROJECT_LOCK.md`、canonical 输入、安全与治理控制；full/security gate 完全不读它。

---

## 9. 历史命令与已移除路径

研究档案和旧状态快照会保留当时存在过的脚本、hook、memory layer、CI 或 subject 同步命令。
执行旧命令前先确认目标路径当前存在并查看 `--help`。路径不存在时，不得从历史文字推断“它应该仍在”，
也不要只为修复旧引用而重建一套未经 owner 设计的新权威面。

`docs/subjects/` 是历史遗留的人工主题投影，不是由 `scripts/sync_doc_subjects.py` 自动生成的树。
当前知识发现入口是 `docs/CATALOG.md`，状态入口是 `docs/CURRENT.md`，推理分类与回填覆盖入口是 `docs/REASONING_LEDGER.md`，历史失效、修复与显式换代入口是 `docs/VALIDITY_LEDGER.md`。新增研究包先登记 dossier，
新增可复用结论先登记 claim；旧结论失效、修复或换代时同时登记 `validity_profile` 与 successor，再生成投影。
