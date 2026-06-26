# Endfield IndustrialPlanner certified-exact 求解器

本仓库研究并实现《明日方舟：终末地》70×70 基地排布的精确空矩形搜索。目标是 `max_lex(area, min_side)`，也就是先最大化空矩形面积，再最大化短边。代码包含 CP-SAT master、binding、routing、campaign 持久化、终端证据复验和发布面校验。

“求解器支持认证路径”不等于“当前项目已经获得认证”。只有在完整候选域耗尽、终端固定 witness 复验、supervisor seal、发布闸和人工 phase gate 全部通过后，公开面才有资格携带 proof-bearing `CERTIFIED`。截至 2026-06-26，P1.2 仍未闭合，P1.3 主集成仍被阻塞。

## 当前发布链状态

当前工作树以未提交的 PR1 发布面 soundness 修复为准，核心控制流是：

```text
outer_search producer
  -> 写入 CANDIDATE_PROPOSED 提案和 proposal-ready marker
  -> [当前仓库没有生产 supervisor CLI/launcher]
  -> ExactCampaign.supervisor_seal() 由独立 supervisor 显式调用后，才可从 checkpoint 字节铸造终端 CERTIFIED
  -> certified_surface.publish_verified_certified_delivery_surface()
     从 supervisor-sealed、磁盘当前的 campaign authority 发布 canonical artifacts
```

已经落地的边界包括：

- producer 不再直接铸造终端 `CERTIFIED`；`outer_search` 的终端结果先写成 `CANDIDATE_PROPOSED`。
- `ExactCampaign.supervisor_seal()` 是持久化终端 `CERTIFIED` 的唯一 mint 点，并在提交前后复核磁盘 authority；但当前工作树没有生产入口调度它，`main.py` 只返回 `CANDIDATE_PROPOSED`。
- fixed-witness binding/routing verifier 已接入 supervisor seal。
- `certified_surface.resolve_p1_2_publish_open_gate()` 已把 P1.2 发布闸接入公开面，open 时 fail-closed。
- canonical `final_solution.json`、`optimal_blueprint.json`、`certified_delivery_manifest.json` 只允许由中央 verified publisher 事务式发布；失败时清理整套公开工件。
- whole-layout nogood 已接独立 infeasibility reverify；无法独立确认时不落 proof-bearing cut。

仍然开放的边界包括：

- 生产 supervisor 调度入口尚未实现；目前只有类方法和测试调用，不能把一次普通 `main.py` 运行描述为“已 supervisor-sealed”。
- PR2 设计中的 L0/L1 最小可信 supervisor、受控 loader、child read-once 和完整 import-closure/TCB 收敛尚未实现。
- review package 默认测试覆盖仍不完整，treeish materialization 仍有可变引用 TOCTOU，归档内容策略仍未覆盖全部外审要求。
- `data/review_gates/phase_1_2_spike_close.json` 仍为 `blocked_manual_review_count`，`p1_3b_entry_allowed=false`。历史机器标识保留 `p1_3b_*`，面向人的当前阶段名称统一写作 P1.3。
- 三次 clean-review 的人工计数是 **owner-maintained outside the repo**；仓库内 receipt 和历史 review 路径只供信息审计，不能自行打开 P1.3。

详见 `PROJECT_LOCK.md`、`docs/certified_proof_chain_analysis.md`、`docs/项目说明/06_current_status.md` 和 `docs/项目说明/soundness_gap_roadmap.md`。

## 精确性边界

- `certified_exact` 与 `exploratory` 严格分离，探索性结果不得升级为认证证据。
- exact 目标为 `max_lex(area, min_side)`；`min_side >= 6` 是候选 admissibility，不是 tie-break。
- exact 模式没有硬编码的“50 供电桩 + 10 协议箱”上限。
- binding 和 routing 是命题 P 的 gating 子问题。`src/models/flow_subproblem.py` 仅用于诊断，不门控 certified 结果，也不生成 proof-bearing cut。
- 当前发布链修复只收窄“谁能铸证、谁能发布”的边界，不证明吞吐、带宽或其它 `PROJECT_LOCK.md` 明确排除的性质。

## 冻结输入

当前工作树已包含 `data/preprocessed/candidate_placements.json`：

- size: `45,773,799` bytes
- SHA256: `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`

它仍是冻结 source-of-truth 工件。其它发行包可以省略该大文件，但 certified exact 运行前必须恢复完全相同的字节，不能使用旧 hash 工件替代。

## 文档入口

- `PROJECT_LOCK.md`: 当前 exactness、发布权和 forbidden-change 契约。
- `docs/README.md`: 文档树及权威边界。
- `docs/项目说明/README.md`: 项目说明书目录。
- `docs/certified_proof_chain_analysis.md`: 当前代码的认证发布链审计。
- `NAV_MAP.md`: 按实际调用和 authority 角色找代码。
- `CLAUDE.md`、`AGENTS.md`: 仓库操作与协作记忆规则。

`docs/subjects/` 和 `DOC-SUBJECT` 注释是历史遗留的人工维护文本。仓库中不存在 `scripts/sync_doc_subjects.py`、`scripts/check_doc_tree_completeness.py` 或 `cc_context/`，preflight 也不执行这些旧投影工具。

## 常用命令

```bash
# Linux 生产入口，带 readiness gate 和运行时调优
bash scripts/run_campaign_linux.sh --campaign-hours 168.0 --parallel-processes 4

# 开发运行
python main.py --campaign-hours 168.0 --parallel-processes 4

# 测试收集
python -m pytest --collect-only -q src/tests

# 全测试
python -m pytest src/tests -q

# P1.2 机器义务
python scripts/check_p1_2_proof_obligations.py
python scripts/check_strong_status_write_allowlist.py
```

截至 2026-06-26，本工作树可收集 425 个测试文件、3450 个测试。这个数字是 collect-only inventory，不是本次审计对完整测试套件通过状态的声明。

## IndustrialPlanner 交付面

IndustrialPlanner viewer、adapter、report 和 bundle 属 postprocess/delivery surface。它们不得重定义 solve schema，也不得从 caller-memory、自报状态或旧工件生成公开 `CERTIFIED`。活动单基地仍为 `valley4_protocol_core`；其它 base 或 outer-deployment 维持 `future_scope`。交付面索引见 `data/examples/industrial_planner/README.md`。
