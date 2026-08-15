# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

《明日方舟：终末地》70×70 基地的 **certified-exact 最大空矩形求解器**（Python 3.13 + OR-Tools CP-SAT）。
入口 `main.py`，默认 `--mode certified_exact`。

姊妹文件 `AGENTS.md` 是 Codex 侧的同责指令（内容更细），两份都改时保持一致；两份目前都是 untracked，
而本仓共享工作区里 untracked 文件会被并发会话清掉——**写完有价值的东西尽快进 commit**。

---

## owner 画像（知识，不是规范）

owner 完整跟着本项目走过来，但自述对每个细节**只保留大概印象**——「像做梦梦到过这个项目的人」，不是记得每个坐标的人。对 owner 讲解时有效的形态是**抽象但不省略信息**：讲道理、结构和结论，不落到 file:line、内部代号或批次号；术语一出现就用一句话说它是什么。owner 数学敏感度高（能当场问出「只留数字怎么固定定理」这种直指要害的问题），所以可以用精确的概念结构，不能用的只是项目内部坐标系。两条实测判据：owner 说「听不懂」，通常不是不够浅，而是**中间断了一环铺垫**（owner 原话「感觉断了什么东西」）；owner 复述时若发现你换了名字或顺手简化了结构，会被迫多做一层翻译。给 owner 的每份讲述先自查：一个只有大概印象的人能不能从第一句顺着走到最后一句、不需要回头查任何东西。

---

## 0. 权威顺序（先读这条）

1. `PROJECT_LOCK.md` — exactness 边界、命题 P、Accepted Invariants、Forbidden Changes。
   与本文件、任何文档或 docstring 冲突时，**以它为准**。
2. `data/proof_obligations/p1_2_proof_obligations.json` — P1.2 机器义务、proof-bearing sink 清单、source/hash floor。
3. `data/review_gates/phase_1_2_spike_close.json` — owner 手动 phase gate（当前 `closed_manual_owner_decision`，
   P1.3 entry allowed）。**只认显式 `owner_manual_decision`**。
4. `docs/项目说明/06_current_status.md` — 人类可读现状；坐标速查 `27_status_dashboard.md`；
   排期与 owner 拍板 `00_master_roadmap.md`；名词消歧 `21_glossary.md`；坑册与 SOP `28_pitfalls_and_sop.md`。
5. 其余 `docs/` / `specs/`。`README.md` 自 2026-08-09 起是当前状态报告（头部写明核验基线日期），
   但权威仍低于 lock 与机器状态。`CHANGELOG.md`（停更于 2026-08-02）与 `docs/research/**` 是带日期的
   历史快照——里面的「当前 / 已闭 / 测试数 / commit hash」只对写下那一刻成立。

**绝不能从绿灯推导关门。** checker PASS、preflight 全绿、测试全过、`supervisor_seal()` 方法存在——
都只说明「登记结构未漂移」，不构成 soundness 证明、不构成 owner 关门动作、不构成 release closure。
P1.2 clean-review 计数由 owner 在**仓库外**维护，仓库内 receipt 是 informational_record_only，
不得从 receipt / 绿灯反推关门进度。

git 历史于 2026-08-09 空白重建（当前只有个位数提交）；文档里引用的旧 commit hash 一律不可
`git show`，只能当叙事线索。原 820-commit 库备份在 `/home/zhuran24/zmd-pj-cc-backup-20260809/`。

---

## 1. 解释器：必须用 `.venv/bin/python`

系统 python 没有 `ortools` / `mypy` / `ruff`，`main.py` 直接 `ModuleNotFoundError`。preflight 第 0 道
解释器自检 fail-closed（判据是能力：Python ≥ 3.13 且 `jsonschema / mypy / ortools / pytest / ruff / yaml`
全可导入）。更要防的是**装了部分依赖的解释器让门禁报绿、但检查面不是项目要求的那套**。
本文所有 `python` 一律指 `.venv/bin/python`。

依赖锁在 `requirements.lock.txt` + `requirements-dev.lock.txt`；没有 `pyproject.toml`，
配置分散在 `ruff.toml` / `pytest.ini`。

---

## 2. 常用命令

### 门禁（唯一权威验收面）

```bash
.venv/bin/python scripts/preflight_gate.py              # staged 范围快检
.venv/bin/python scripts/preflight_gate.py --full       # 全量 gate + 全部 pytest（仍固定追加 -m "not slow"）
.venv/bin/python scripts/preflight_gate.py --slow-tests # 专用慢 soundness lane（-m slow，串行，长超时）
.venv/bin/python scripts/preflight_gate.py --ci --base-ref origin/main   # 按 diff 范围
```

### 测试

```bash
# 单文件 / 单 nodeid 的标准形态（固定顺序 + 独立 basetemp，防并发互删）
.venv/bin/python -m pytest -p no:randomly --basetemp=.pytest_tmp/one -q src/tests/test_exact_contract.py
.venv/bin/python -m pytest -p no:randomly --basetemp=.pytest_tmp/one -q \
    "src/tests/test_exact_contract.py::test_exact_mode_uses_flow_only_as_diagnostic"

# 快 lane 手动重现（跨核并行）
.venv/bin/python -m pytest -q -m "not slow" -n auto src/tests/
```

### 单点 checker（定位 drift 比全量快）

```bash
.venv/bin/python scripts/check_p1_2_proof_obligations.py        # close-kernel 结构 + V99 source-sha
.venv/bin/python scripts/check_strong_status_write_allowlist.py # strong-status 写点 deny-by-default
.venv/bin/python scripts/check_phase_review_gate.py             # owner phase gate 形态
.venv/bin/python scripts/check_external_artifacts.py --require candidate_placements
.venv/bin/python devtools/check_repository_code_assets.py check # 代码资产分类/投影
```

### lint / 类型

```bash
.venv/bin/python -m ruff check .        # 全仓，任何 warning 都 BLOCK
.venv/bin/python -m mypy --explicit-package-bases --ignore-missing-imports --follow-imports=silent <targets>
```

mypy 只 strict 到 `MYPY_STRICT_TARGETS`（列在 `scripts/preflight_gate.py`）。

### 求解 / 发布 / 外部工件

```bash
.venv/bin/python main.py --mode certified_exact --campaign-hours 8   # 只会停在 CANDIDATE_PROPOSED
.venv/bin/python main.py --mode exploratory                          # 启发式/诊断，永不能升为证明
.venv/bin/python scripts/run_supervisor_seal.py                      # 唯一 durable CERTIFIED mint 生产入口
bash scripts/run_campaign_linux.sh                                   # wrapper，自动注入 --resume-campaign

# data/preprocessed/candidate_placements.json（54MB 外部大工件）轻量副本可能缺失：
.venv/bin/python scripts/check_external_artifacts.py --require candidate_placements
.venv/bin/python scripts/restore_external_artifacts.py candidate_placements --source <file> --force
```

---

## 3. 命令坑（都被实测坐实过）

- **preflight 退出码只有 0/1**，没有 2。判 BLOCK 看 blockers 非空或输出里的 `BLOCK` 行。
- **`--full` 不是全部测试**：固定追加 `-m "not slow"`。改认证核心（producer / seal / publish /
  checker / V99 钉死的源文件）后**必须另跑 `--slow-tests`**，否则慢 soundness 是盲区。
- **`@slow` 是集中登记**：名单在 `src/tests/conftest.py::_SLOW_TEST_NODEIDS`。新写 ≥8s 的测试要去登记。
- **并发 pytest 会互删临时目录**：全局 `--basetemp=.pytest_tmp` 共用，多进程时各自覆盖为独立子目录。
- **要可复现顺序永远显式 `-p no:randomly`**（`pytest-randomly` 装没装决定默认顺序）。
- **缺 `candidate_placements.json` 是硬失败不是 skip**：`test_binding.py` / `test_routing.py` 若干用例
  fixture 阶段直接 `FileNotFoundError`。看到一批测试莫名 error 先查这个工件。
- **验收要看 skip 数字**，不只看 passed；静默 skip 比红更危险。
- **认证链测试在跑时整棵树必须冻结**：source digest 是字节级的且范围大于 sealed 名单，慢 lane /
  preflight 期间任何 `src/` `scripts/` 改动（含只改 docstring、一次 `git commit`）都会跑成假红。
  长门禁发射前先提交完，跑起来后只做树外工作；看到认证链测试莫名红先 `git status`。
- **`--exploratory` 会覆盖 `--mode`**；exploratory 在 prod-scale 上不可用（build 爆炸）。
- **`scripts/production_readiness_gate.py` 不是纯只读**（面向 CachyOS/pacman，会 `mkdir .artifacts`）。
- **跑完 `main.py` 只会得到 `CANDIDATE_PROPOSED`**——刻意的操作链缺口，不是 bug。
- **门禁/测试命令永远 `> log 2>&1` 全量落文件**，别 `| tail`（裁掉失败细节且退出码被顶成 0）。
- 后台命令 timeout 被 clamp 到 600s。>10min 的活写成脚本 `setsid nohup script.sh &`，
  末尾 `touch <名>.DONE` 并把退出码写进日志，用标记文件判终态（别用日志哨兵、别用 `pgrep -f`）。

---

## 4. 大图架构

### 4.1 唯一最重要的规则：`certified_exact` vs `exploratory` 严格隔离

只有 certified_exact 能产证明材料；exploratory 的 cap/hint/probe/sidecar **永不能升格为证据**。
三条 Forbidden Change：① exploratory cap/hint 不得当精确上下界（hint 只允许写 CP-SAT
`solution_hint` proto，永不写约束）；② flow 模型（`flow_subproblem.py`，连续 LP/GLOP）
**diagnostic-only、永不 gate**——有契约测试 monkeypatch flow→INFEASIBLE 仍断言 CERTIFIED；
③ postprocess/serializer/viewer/adapter 不得成为发布权威。

`min_side >= 6` 是候选 admissibility 规则（权威在 `rules/canonical_rules.json`），不是目标 tie-break。
空矩形语义（owner 2026-08-05 裁决）：矩形内不得有**任何**占用物（设施、供电桩、传送带、跨接件）。
exact 模式没有「50 供电桩 + 10 协议箱」硬 cap（那是 exploratory 示意值）。

### 4.2 producer / supervisor / publisher 三分权（PR1）

任何单一写方都铸不出 public `CERTIFIED`：

```
main.py → run_solve() → src/search/outer_search.py
  PRODUCER   跑搜索，terminal 只提交 CANDIDATE_PROPOSED + 证据材料
    └ src/search/benders_loop.py                Benders / LBBD 主循环
       ├ src/models/exact_coordinate_master.py  默认 certified placement master (CP-SAT)
       ├ src/models/binding_subproblem.py       CERTIFIED GATE：端口绑定 + exact-count
       ├ src/models/routing_subproblem.py       CERTIFIED GATE：栅格路由（连通，不是吞吐）
       ├ src/models/flow_subproblem.py          DIAGNOSTIC ONLY —— 永不 gate
       ├ src/search/independent_infeasibility_reverifier.py  nogood 落 cut 前独立复验
       └ src/cuts/lifecycle.py                  cut 生命周期；attach 在 certified 下 default-off

scripts/run_supervisor_seal.py → ExactCampaign.supervisor_seal()
  SUPERVISOR 唯一 durable terminal CERTIFIED mint：从磁盘读提案，写前写后各验一次

publish_verified_certified_delivery_surface()   （src/search/certified_surface.py）
  PUBLISHER  唯一 public 发布器：sealed + disk-current + gate-passed 后同一事务派生三件交付物
```

**方法存在 ≠ 入口存在 ≠ release closure。** 项目至今**从未产出过任何 durable CERTIFIED**
（`data/blueprints/` 不存在是常态，不是坏了）。

### 4.3 命题 P：CERTIFIED 证 6 条 gating 谓词 + lex 最优性

证：① ghost 内无 facility；② 两两不重叠；③ per-instance placement_rule；④ 端口绑定含端口级
exact-count；⑤ 路由 = 离散有向连通 + route cell 在矩形外（**不是吞吐**）；⑥ 供电覆盖
（塔覆盖矩形与受电 footprint **相交** ≥1 格，非包含，另有独立 terminal 复验）。

不证（冒充即 Forbidden Change）：物料离散吞吐 / 带宽容量；~98% 密度下的容量连通；机器间物理间隙
（`machine_min_clearance_cells=1` 管端口 connector 格，机身贴身合法）。

### 4.4 cut framework 现状（P1.3）

F1/F6/F7 typed lowering 全链；F5 shadow-only（结构上改不了 master）；F2/F3/F4/F9
LEGACY_DIAGNOSTIC（registry 边界即拒）；F8 已退役。`EXACT_CUT_FRAMEWORK_ATTACH` 在 certified 下
unsafe-map 禁用 / default-off，**B6 owner promotion 未做**。feature toggle 一律走 `EXACT_*` 环境变量
（清单见 `docs/项目说明/18_workflow_env_config.md`）；certified 路径检测到 unsafe override 即 fail-closed。

### 4.5 目录职责

| 目录 | 角色 |
|---|---|
| `src/search/` | outer producer、campaign、frontier、fixed-witness、supervisor seal、中央发布面 |
| `src/models/` | master / binding / routing；flow 仅诊断 |
| `src/cuts/` | F1-F7+F9 cut 生成/校验/生命周期 |
| `src/io/` | strict JSON、序列化、delivery manifest；不单独拥有发布权 |
| `src/render/`, `src/adapters/` | postprocess/交付面，必须消费中央验证后的 authority |
| `src/ai_accel/` | AI 加速面；preflight 逐行扫禁 `data/checkpoints|solutions|blueprints` 字样 |
| `src/tests/` | 单元 / 回归 / soundness 红测 |
| `rules/`, `data/preprocessed/` | canonical rules 与冻结输入 |
| `data/proof_obligations/`, `data/review_gates/` | P1.2 机器义务；owner 手动 phase gate |
| `devtools/` | 仓库治理与研究运行契约（非 certified TCB） |
| `.artifacts/`, `docs/research/` | 一次性评审证据与历史研究档案，不是活代码（ruff 已 exclude） |

调用链细节见 `NAV_MAP.md`；建议阅读顺序也在那里。

---

## 5. Frozen artifacts 与 freeze-ritual

字节级钉死的输入（清单权威 = `scripts/preflight_gate.py` 的 `FROZEN_ARTIFACTS` /
`EXTERNAL_FROZEN_ARTIFACTS`；runtime 侧 `src/search/certified_artifact_contract.py`）：
`rules/canonical_rules.json`、`rules/preprocess_plan.json`、`data/preprocessed/` 下
`mandatory_exact_instances.json` / `generic_io_requirements.json` / `candidate_placements.json`。

> 本文件**刻意不抄任何 sha / 字节数**——需要真值时从上面两个源码位置取，
> 或 `git show HEAD:<file> | sha256sum`。

**mismatch 时绝不「好心」更新 expected 值**——pin 是身份声明不是校验和；历史多代
hash-incompatible 工件必须被 `artifact_hash_mismatch` 拒绝。只有确实换代的批才走 freeze-ritual，
**单改一个 expected 常量永远是错的**。

改任何被钉字节（5 个冻结工件、V99 名单源文件、`PROJECT_LOCK.md`、`scripts/preflight_gate.py`）
= 走完整 freeze-ritual：`git grep` 搜**旧值本身**（大小写不敏感）判定 pin 面 → 先清 ruff →
Edit 工具改字节（**绝不 `write_text`/`json.dump`**，行尾会炸）→ 重生成派生产物 → pin 走迭代法
（填一处→重跑 checker→报下一处）→ 两个结构 checker + `--full` + `--slow-tests` 全绿 →
精确 pathspec 提交。四条 reseal 连锁（链 A 冻结工件 / 链 B V99 源文件 / 链 C preflight_gate 自身 /
链 D PROJECT_LOCK.md 的 6+1）的完整清单见 `AGENTS.md` §6 与 `docs/项目说明/28_pitfalls_and_sop.md` SOP-1/2。

---

## 6. git 纪律（共享工作区）

求解产物不进 git（`FORBIDDEN_STAGED_PATHS`）：`data/checkpoints/`、
`data/blueprints/optimal_blueprint.json`、`data/solutions/final_solution.json`、
`data/solutions/certified_delivery_manifest.json`。注意 `data/solutions/` **不是整目录忽略**。

本仓常有并发会话共用同一工作区和 `.git/index`：

- **裸 `git commit -m` 会把别人 staged 的文件一起提交**。提交前重看 `git status --short`，
  只用带精确 pathspec 的提交，pathspec = 这次逻辑改动的完整一致集。
- **`--amend` 前先 `git log --oneline -1` 比对 hash**（HEAD 可能已被别的会话推进）。
  误 amend 用 `git reset <对方hash>`（mixed，**别 `--hard`**）再精确重提。
- **untracked 文件会消失**（并发会话清理会带走）。安全线是「进了 commit」，写完立刻提交。
- `scripts/package_review_snapshot.py` 打的是已提交树，外审打包前先提交。
- 本地没有 git hook（`.githooks/` 不存在），门禁靠手动跑 `preflight_gate.py`。

---

## 7. 搜索约定

```bash
rg -n '<keyword>'                    # 开发者视角，遵守 .rgignore 投影
git grep -n -I -e '<keyword>' --     # 全部 tracked 路径，忽略 .rgignore
```

**承重结论一律 `git grep` 起手；「rg 搜不到 = 不存在」在本仓不成立**，三种系统性漏报：
① `.rgignore` 把 `docs/research/**` 的脚本整类排出，而其中混着被 `src/tests/` 真导入的活契约；
② pin 值可能是相邻字符串拼接写的，grep 完整字面量零命中；③ 同一 sha 在不同文件大小写不同。
非要 rg 就带 `--no-ignore --hidden` 并排除 `.git/` `.artifacts/` `.pytest_tmp/`。
查集合成员资格用 python import 把集合 print 出来或跑对应契约测试，别只 grep 字面量。

---

## 8. 当前工作树的「已下线」

这些在 `README.md` / `docs/research/` / doc 28 里仍被大量引用，但**当前树里不存在**，按下线处理：

- **记忆层整体移除**（2026-08-09）：`cc_memory/` 与 `cc_memory_vnext/` 都不在树里；preflight 记忆
  lane 有意留白（`MEMORY_TEST_DIRS` 为空只 warn）。`devtools/memory_*.py` 仍在但操作仓库外目录。
- **`.codegraph/` / `.claude/` / `.Codex/` 不在树里**：codegraph 索引、hook 接线均无对应文件。
- **`.github/` 已移除**：CI 重建时要把 workflows 加回 `data/line_ending_policy.json` 的 `required_lf_globs`。
- **已退役文档工具**：`sync_doc_subjects.py`、`check_doc_tree_completeness.py` 不存在；
  `docs/subjects/` 与 `<!-- DOC-SUBJECT:... -->` 是历史遗留手工文本。

用研究日志里的旧命令之前，先确认脚本还在、看当前 `--help`。
