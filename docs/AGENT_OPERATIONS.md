# Agent 操作手册

本页是 tracked 的耐久 agent 操作与文档维护指南；根 `CLAUDE.md` / `AGENTS.md` 仅在本机存在时作为轻量 workspace overlay。只有任务触及测试、门禁、冻结资产、求解、发布、cut 生命周期、Git 修复或复杂故障时才加载本页。当前 gate、上下界、hash、测试数量和开关状态一律回到 [`CURRENT`](CURRENT.md) 或对应机器源，不在这里维护副本。

## 1. 解释器与环境

所有项目 Python 命令使用 `.venv/bin/python`；不要用裸 `python`、`python3` 或临时解释器替代。preflight 会先检查解释器能力，能力不满足时 fail closed。
环境问题先运行 `.venv/bin/python -c "import sys; print(sys.executable); print(sys.version)"`。

外部大工件可以在轻量 checkout 中缺失。恢复方式、下载来源和完整性要求见 [`.artifacts/README.md`](../.artifacts/README.md) 与相关 dossier；不要为了让测试通过而伪造空文件或占位 hash。

```bash
.venv/bin/python scripts/restore_external_artifacts.py candidate_placements --source <file> --force
```

## 2. 文档与知识事务
文档操作始终从目标路径的有效契约开始：
```bash
.venv/bin/python devtools/docctl.py context <path> --intent edit
```
写入与显式生成完成后：
```bash
.venv/bin/python devtools/docctl.py intake --changed
.venv/bin/python devtools/docctl.py check --changed
.venv/bin/python devtools/check_knowledge_docs.py
```
`intake` 从 Git-visible diff 识别新增文档、生成页穿透、dossier 登记/关闭、owner authority companion、稳定 claim/decision 身份、临时文档和 local-optional portability。当前缺少 authority companion 只产生 default-off warning，不能被解释为授权；未来由 registry 开关提升为阻断。它只展示本次任务需要的事件卡，`check --changed` 复用同一结果。
新增研究包优先使用 `docctl new research-dossier`，它会同时创建入口和 `active` ledger record。关闭前先建立 current review 与必要 claim/decision，再用 `devtools/docctl.py close-dossier` 写 typed closure。新本机 evidence 使用 `devtools/docctl.py register-local-evidence`，临时稿使用带 expiry/exit action 的 `docctl new document` 并由 `devtools/docctl.py exit-ephemeral` 退出。不要建立第二份局部 dossier 真源。
claim 的 `representation_class`、`authority`、`authority_basis` 和 evidence `storage` 是四个不同维度。只有 knowledge checker 能对 tracked machine source 实际执行具名 verifier 的记录才能标为 `machine`；历史 receipt 封顶 `research_authority`。`decisions.jsonl` 是 `non_authorizing` 追加登记册，必须指向外部 owner source，不能单独授权；schema 迁移只按 intake registry 中的精确 absent→present 字段豁免稳定身份检查。
生成页、兼容跳转和职责索引不能直接修补，应修改其声明的 source，再运行操作卡给出的 generator。前门 registry 变化时使用：
```bash
.venv/bin/python devtools/docctl.py render-entrypoints --write
```
周期盘库只读现有真源，不另建维护状态；接受 finding 后仍修改原 claim、review、triage、policy 或 lifecycle 真源。每周运行 `.venv/bin/python devtools/docctl.py audit --profile weekly`，phase close 使用 `--profile phase_close --as-of YYYY-MM-DD`，修复后重建 `MAINTENANCE_QUEUE.md`。
## 3. 门禁、测试与静态检查

### 3.1 文档治理门
文档、知识、policy 或框架工具交付前运行共享只读门：
```bash
.venv/bin/python devtools/docctl.py gate --profile changed
.venv/bin/python devtools/docctl.py gate --profile full  # phase boundary / 当前树全量
.venv/bin/python devtools/docctl.py gate --profile historical_replay  # 手工历史 object replay
.venv/bin/python devtools/document_governance_gate.py list --json
```
`changed` 验证当前职责、知识、引用、artifact evidence、current code-assets、回归、ruff 与 mypy；`full` 扩大当前树验收面，但不运行冻结历史 replay。历史对象复验只通过手工 `historical_replay` profile 执行，并要求完整仓外 Git object graph。对已经提交且工作树干净的分支加 `--base <merge-base>`，CI 会自动提供。生成页必须先显式 `render --write`。runner 为 lane 分配独立仓外临时目录，并要求前后 Git-visible fingerprint 相同。该门不替代 production preflight，也不授予数学或 owner authority。
### 3.2 Preflight

门禁入口是 [`scripts/preflight_gate.py`](../scripts/preflight_gate.py)；参数与检查面以脚本当前实现为准。
```bash
.venv/bin/python scripts/preflight_gate.py                         # staged 快检
.venv/bin/python scripts/preflight_gate.py --full                  # 全量非 slow
.venv/bin/python scripts/preflight_gate.py --slow-tests            # 慢 soundness lane
.venv/bin/python scripts/preflight_gate.py --ci --base-ref origin/main
```

`--full` 不等于包含 slow marker 的全部测试。改变 producer、seal、publish、binding、routing、cut replay 或其他认证承重路径时，必须根据改动面补跑 slow lane 和定点 soundness 测试。

长命令应完整落日志：

```bash
.venv/bin/python scripts/preflight_gate.py --full > /tmp/zmd-preflight.log 2>&1
status=$?
cat /tmp/zmd-preflight.log
exit "$status"
```

不要把命令直接管给 `tail`，否则失败上下文和真实退出码可能被裁掉。

后台命令 timeout 被 clamp 到 600s。预计超过 10 分钟的任务使用独立 wrapper，以 `setsid nohup` 启动并完整重定向 stdout/stderr；wrapper 末尾把真实退出码写进日志，并在所有收尾完成后创建 `.DONE` 标记。终态以退出码日志与标记文件联合判定，不用日志哨兵或 `pgrep -f` 猜测进程是否完成。后台任务运行期间不得启动会争用同一输出、临时目录或认证源树的副本。

### 3.3 Pytest

单文件或单 nodeid 使用独立 basetemp：

```bash
.venv/bin/python -m pytest -p no:randomly \
  --basetemp=.pytest_tmp_target -q path/to/test_file.py

.venv/bin/python -m pytest -p no:randomly \
  --basetemp=.pytest_tmp_target -q path/to/test_file.py::test_name
```

跨 lane 并行时，每个进程必须使用不同 basetemp；全局共享 `--basetemp=.pytest_tmp` 会导致并发进程互删目录。需要可复现顺序时显式加 `-p no:randomly`，不能依赖本机是否安装 `pytest-randomly`。验收不仅看 passed，也看 skipped、xfailed、errors 和 collection 结果。外部依赖缺失若会破坏认证结论，应 fail closed，而不是静默 skip。

认证链测试、slow lane 或 preflight 运行期间，冻结其 source digest 覆盖的整棵源树；不要同时修改 `src/`、`scripts/`，也不要在测试中途提交这些字节。承重测试出现无解释的 source identity 失败时，先检查工作树是否被并发会话改动。

### 3.4 单点 checker

```bash
.venv/bin/python scripts/check_phase_review_gate.py
.venv/bin/python scripts/check_p1_2_proof_obligations.py
.venv/bin/python scripts/check_strong_status_write_allowlist.py
.venv/bin/python scripts/check_external_artifacts.py --require candidate_placements
.venv/bin/python scripts/check_line_endings.py
.venv/bin/python devtools/check_knowledge_docs.py
.venv/bin/python devtools/docctl.py doctor
.venv/bin/python devtools/docctl.py check --changed
.venv/bin/python devtools/docctl.py audit --profile weekly
.venv/bin/python devtools/docs_reference_scan.py validate-registry
.venv/bin/python devtools/check_repository_code_assets.py check-current
.venv/bin/python devtools/check_repository_code_assets.py check
```

checker 只证明它声明的结构没有漂移。仓库内 review receipt 是 `informational_record_only`，clean-review 计数由 owner 在仓库外维护；receipt 或 PASS 不能换取 clean-review 计数、owner decision 或 release closure。checker 不替代数学证明、外审、owner decision 或 release authority。

### 3.5 Lint 与类型

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy <target paths>
```

严格类型范围以 preflight 中的机器配置为准，不在文档中复制当前 target 列表。

## 4. 求解、复验与发布

默认 certified 入口和实际参数以 `main.py --help`、[`PROJECT_LOCK.md`](../PROJECT_LOCK.md) 和 [`CURRENT`](CURRENT.md) 为准。常见入口：

```bash
.venv/bin/python main.py --mode certified_exact
.venv/bin/python scripts/run_supervisor_seal.py
```

`--exploratory`、hint、cap、probe、sidecar、best-effort resume、诊断 flow 和研究 cut 都不能成为 certified 证明材料。`--skip-readiness-gate` 只跳过它明确声明的启动检查，不应被解释为绕过冻结监控、sink replay、seal 或 publication 条件。

候选、supervisor seal 与 publisher 的职责必须分开：

1. producer 产生候选与 proof-relevant 材料；
2. supervisor 从磁盘当前状态独立复验并铸造 durable terminal 状态；
3. publisher 只发布与 seal 同源且满足 owner/release gate 的表面。

任何中间文件写着 `CERTIFIED`，都不能凭字符串本身获得终局 authority。

## 5. 认证命题与模块边界

当前 theorem scope、active base、canonical semantics、研究 ledger 和 cut attach 状态统一从 [`CURRENT`](CURRENT.md) 读取。稳定的命题边界在 [`PROJECT_LOCK.md`](../PROJECT_LOCK.md)、[`specs/01_problem_statement.md`](../specs/01_problem_statement.md) 和 [`docs/项目说明/01_overview.md`](项目说明/01_overview.md)。

常用目录职责：

| 路径 | 职责 |
|---|---|
| `src/models/` | master、binding、routing 与诊断模型 |
| `src/cuts/` | cut 生成、验证、typed lowering 与生命周期 |
| `src/search/` | exact campaign、frontier、seal 与发布链 |
| `src/tests/` | 单元、回归、soundness 与治理红测 |
| `data/proof_obligations/` | fail-closed 证明义务与 source/hash floor |
| `data/review_gates/` | owner-only phase gate |
| `data/knowledge/` | claim、decision、dossier、topic 与术语真源 |
| `docs/research/` | 历史研究和外审证据，不自动成为当前 authority |

更细的代码入口见 [`NAV_MAP.md`](../NAV_MAP.md)。

## 6. Cut framework 操作边界

cut 的候选发现、选择、数学有效性验证、typed lowering、runtime attach 与 owner promotion 是不同义务。typed pipeline 能消费已提供且验证通过的 cut，不等于它会自动发现有效不等式，也不等于通用 CP-SAT 传播已经完成同样的分离。

任何 certified attach、默认值或 family authority 变化必须：

1. 查询目标文件的 `docctl context`；
2. 读取 [`PROJECT_LOCK.md`](../PROJECT_LOCK.md)；
3. 对照 [`CURRENT`](CURRENT.md) 中的 production 边界；
4. 完成 family validation、scope resolution、lowering、replay、回归与 owner 流程；
5. 不把实验零激活、预算耗尽或 producer 未到达写成数学不可能性。

推理和分离证据边界见 [`REASONING_LEDGER`](REASONING_LEDGER.md) 与 [`OPEN_QUESTIONS`](OPEN_QUESTIONS.md)。

## 7. Frozen artifacts 与 freeze ritual

冻结清单和 expected hash 的机器 authority 位于 `scripts/preflight_gate.py`、认证契约代码和 proof-obligation records。需要真值时直接读取这些源，或对目标 revision 使用：

```bash
git show HEAD:<path> | sha256sum
```

看到 hash mismatch 时，不要“顺手更新 expected”。pin 是身份声明，不是当前文件校验和。先判断：

- 文件是否意外变化；
- 变更是否得到 owner/规范授权；
- 哪些测试、source digest、manifest、proof obligation 和文档展示值依赖该字节；
- 是否需要完整 reseal。

改动冻结资产或其 pin 链时遵循：

1. 用 `git grep -ni '<old hash or symbol>' --` 查 tracked 依赖；确需覆盖未跟踪内容时使用带显式排除项的 `rg --no-ignore --hidden`；
2. 区分活代码/测试 pin、机器义务、文档展示和历史证据；
3. 只更新当前真源及其明确派生物，不改历史快照；
4. 运行目标契约测试，再跑完整 preflight 和所需 slow lane；
5. 长测试期间保持认证链相关 tracked bytes 不变；
6. 提交后重新从提交对象计算 hash，并验证 worktree 干净。

精确联动链会随实现演化，不能依赖旧文档中固定的“若干处 pin”计数。

## 8. Git 与禁提交边界

求解产物、临时 basetemp、日志、缓存、恢复出的本地大工件和其他机器输出通常不进入 Git。具体禁提交规则以 `scripts/preflight_gate.py`、`.gitignore` 和 code-assets registry 为准；`data/solutions/` 等父目录不能仅凭目录名整体推断为可提交或不可提交。

本仓允许多个会话共享同一工作树和 `.git/index`。提交前必须重新检查：

```bash
git status --short
git diff --check
git diff --name-status
git diff --cached --name-status
```

- 暂存使用本任务完整一致集的精确 pathspec，不使用 `git add -A`；提交命令同样携带精确 pathspec。裸 `git commit -m` 会把其他会话已经 staged 的文件一并提交。
- HEAD 可能在任务进行中被其他会话推进。任何 amend、rebase 或纠错前先记录并复核当前 HEAD、目标对象与 diff；误 amend 时用 `git reset <对方hash>`（mixed，别 `--hard`）恢复，再按精确 pathspec 重提。禁止用 `git reset --hard` 或 `git clean` 处理共享工作区，也不能只凭 commit message 猜对象身份。
- untracked 文件可能被并发清理。需要耐久保存的仓库资产应尽快进入精确提交；根 `CLAUDE.md` / `AGENTS.md` 这类 workspace overlay 仍按本地契约处理，不得混入 tracked 提交。
- `scripts/package_review_snapshot.py` 读取已提交树；外审打包前先完成本任务提交，不能把工作树字节误当成快照内容。
- 不在认证长测试运行中修改或提交承重文件。仓库没有可依赖的自动 hook 时必须手动运行门禁；hook 存在也只是辅助，不能替代最终机器验收。

## 9. 常见故障模式

- **测试顺序不稳定**：定点复现加 `-p no:randomly`，不要把随机顺序差异误判为代码修复。
- **basetemp 互删**：并行 pytest 不得共享目录。
- **环境变量残留**：certified 路径可能 fail closed；先检查当前 shell 和 `.env*` 的作用域。
- **外部工件缺失**：先恢复真实 payload 和校验，不创建伪造占位物。
- **预算耗尽**：只能陈述 UNKNOWN、NOT_EXHAUSTIVE、NOT_REACHED 或工具定义的等价状态。
- **长跑测量两口径混用**：周期性 progress 快照是下界不是精确计数；事件精确计数一律以 append-only journal 的完整落盘行为真源，两口径不得混用或相加（在案先例：Phase -1 快照 840 vs journal 7578）。
- **历史路径不存在**：研究日志可能引用已经退役或只在旧工作区存在的 `.codegraph/`、`.Codex/`、`cc_memory/`、`cc_memory_vnext/` 及旧脚本；`.claude/` 当前包含项目 skill，例如 `.claude/skills/solving-methodology/SKILL.md`，不能整目录按退役处理。先查看当前 `--help`、[`NAV_MAP`](../NAV_MAP.md) 和 Git 历史，不为修复旧引用重建未经 owner 设计的 authority surface。
- **搜索假阴性**：承重的存在/不存在结论先用 `git grep` 检查全部 tracked 路径；`rg` 默认受 `.rgignore` 影响，完整 hash 还可能被拆成相邻字符串，同一 sha 也可能在不同文件使用不同大小写。查集合成员资格时优先导入机器定义或运行对应契约测试。
- **生成页漂移**：修改 source 后运行声明的 generator；不要直接编辑输出。
- **文档结论越权**：report、receipt、solver PASS 和 reviewer prose 只能在各自作用域内提供证据。

更完整的项目坑册见 [`docs/项目说明/28_pitfalls_and_sop.md`](项目说明/28_pitfalls_and_sop.md)。

## 10. 任务结束前

至少确认：

```bash
git diff --check
.venv/bin/python devtools/docctl.py intake --changed
.venv/bin/python devtools/docctl.py check --changed
.venv/bin/python devtools/check_knowledge_docs.py
.venv/bin/python devtools/docctl.py gate --profile changed
```

若触及代码、规范、冻结输入、proof obligations、phase gate、求解或发布链，再按目标契约运行定点测试、lint、mypy、完整 preflight 和必要 slow lane。最终报告应区分已通过的机械检查、未运行的检查、环境限制以及仍需 owner 或数学审查的部分。
