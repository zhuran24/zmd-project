# 文档系统失效恢复

这是文档系统的固定自举说明。它只在 `.docsystem/manifest.json` 或 `devtools/docctl.py` 无法正常工作时使用，不替代正常维护流程。

## 最小公理

1. 仓库根目录的 `.docsystem/manifest.json` 是唯一固定入口。
2. 普通文档变更前应运行 `devtools/docctl.py context`，完成写入后应运行 `devtools/docctl.py intake --changed`、`devtools/docctl.py check --changed` 与 manifest-owned 的非变异治理门。
3. `DOC_POLICY.json`、manifest、schema、invariants、`docctl.py`、治理门 registry/runner/CI、框架指南和 ADR 都属于 framework core。
4. framework core 损坏时 fail closed。不要通过直接修改生成页、历史证据或 owner authority 来绕过故障。

## 恢复顺序

从仓库根目录执行：

```bash
.venv/bin/python -m json.tool .docsystem/manifest.json
.venv/bin/python -m json.tool DOC_POLICY.json
.venv/bin/python -m json.tool data/repository_governance/document_system/governance_gate.json
.venv/bin/python -m json.tool data/repository_governance/document_system/intake.json
.venv/bin/python -m json.tool data/repository_governance/document_system/maintenance_audit.json
.venv/bin/python -m json.tool data/repository_governance/document_system/ephemeral_documents.json
.venv/bin/python -m py_compile devtools/docctl.py devtools/document_governance_gate.py devtools/document_maintenance_audit.py
.venv/bin/python devtools/document_governance_gate.py list --json
.venv/bin/python devtools/docctl.py guide
.venv/bin/python devtools/docctl.py doctor
```

如果 `docctl.py` 连启动都失败，按以下固定路径人工读取：

- 当前架构：`docs/governance/document-system/ARCHITECTURE.md`
- 框架维护：`docs/governance/document-system/MAINTAINING.md`
- 常态交接：`docs/governance/document-system/STEADY_STATE.md`
- 设计决定：`docs/governance/document-system/ADR/`
- 核心原则：`data/repository_governance/document_system/invariants.json`
- policy schema：`data/repository_governance/document_system/doc_policy.schema.json`
- 前门注册表：`data/repository_governance/document_system/entrypoints.json`
- 前门 schema：`data/repository_governance/document_system/entrypoints.schema.json`
- 分区注册表：`data/repository_governance/document_system/sections.json`
- 分区 schema：`data/repository_governance/document_system/sections.schema.json`
- 收束验收投影：`docs/CONVERGENCE_REPORT.md`
- 治理门 registry：`data/repository_governance/document_system/governance_gate.json`
- 治理门 schema：`data/repository_governance/document_system/governance_gate.schema.json`
- intake registry：`data/repository_governance/document_system/intake.json`
- intake schema：`data/repository_governance/document_system/intake.schema.json`
- maintenance audit registry：`data/repository_governance/document_system/maintenance_audit.json`
- maintenance audit schema：`data/repository_governance/document_system/maintenance_audit.schema.json`
- maintenance queue projection：`docs/MAINTENANCE_QUEUE.md`
- active ephemeral registry：`data/repository_governance/document_system/ephemeral_documents.json`
- ephemeral schema：`data/repository_governance/document_system/ephemeral_documents.schema.json`
- 治理门 runner：`devtools/document_governance_gate.py`
- 共享 CI 入口：`.github/workflows/document-governance.yml`
- 根 policy：`DOC_POLICY.json`

修复应限制在使 manifest、schema、policy resolver 和定点测试重新一致所需的最小范围。修复后必须运行：

```bash
.venv/bin/python devtools/docctl.py render-legacy --write
.venv/bin/python devtools/docctl.py render-entrypoints --write
.venv/bin/python devtools/docctl.py render-sections --write
.venv/bin/python devtools/docctl.py render-guidance --write
.venv/bin/python devtools/docctl.py render-convergence --write
.venv/bin/python devtools/docctl.py render-maintenance --write
.venv/bin/python devtools/docctl.py doctor
.venv/bin/python devtools/docctl.py intake --changed
.venv/bin/python devtools/docctl.py audit --profile weekly
recovery_tmp="$(mktemp -d -p "$(dirname "$(pwd -P)")" zmd-docsystem-recovery.XXXXXX)"
trap 'rm -rf "$recovery_tmp"' EXIT
.venv/bin/python -m pytest -p no:randomly -p no:cacheprovider \
  --basetemp="$recovery_tmp/pytest" -q \
  src/tests/test_document_system.py devtools/tests/test_document_governance_gate.py
.venv/bin/python devtools/docs_reference_scan.py validate-registry
.venv/bin/python devtools/docctl.py gate --profile changed
```

如果修复改变了框架行为，而不只是恢复原有实现，还必须新增 ADR，并同步 `ARCHITECTURE.md`、`MAINTAINING.md`、schema 迁移和回归测试。

## 治理门自身失效时

先用 `devtools/document_governance_gate.py list --json` 验证 manifest、registry 与 schema 是否可加载，再用 `fingerprint` 读取当前 Git-visible receipt。不要在 runner 失效时把 workflow 改成一组临时手写 checker；那会建立第二套验收面。修复 runner、registry 或 workflow 后，必须运行 `devtools/tests/test_document_governance_gate.py`，再通过 `devtools/docctl.py gate --profile changed`。历史 Git object 不完整时，当前 `changed` / `full` / `weekly` 仍可检查当前树；手工 `historical_replay` 必须继续 fail closed。

## manifest 或 schema 损坏时的固定恢复路径

manifest schema 路径由 `devtools/docctl.py` 与 `devtools/document_governance_gate.py` 固定为 `data/repository_governance/document_system/manifest.schema.json`。manifest 缺失、被改指向其他 schema 或无法解析时，先从当前可信 Git 对象恢复最小自举面：

```bash
git checkout -- .docsystem/manifest.json \
  data/repository_governance/document_system/manifest.schema.json \
  devtools/docctl.py devtools/document_governance_gate.py
```

共享工作区禁止用 `git reset --hard`、`git clean -fdq` 或 `git add -A` 代替定点恢复。`CLAUDE.md` / `AGENTS.md` 是可选 workspace overlay，缺失不应阻断 tracked 系统；真实内容需从本机备份或协作流程调和。历史 replay 只通过手工 `historical_replay` profile 执行，并要求完整仓外 Git object graph。
## 真实仓库补丁落地恢复

真实共享工作区的 tracked、untracked 与 external 拓扑不同于供应快照。不要运行旧补丁包中的破坏性回滚脚本。先读取：

- `data/repository_governance/document_system/landing.json`
- `data/repository_governance/document_system/landing.schema.json`
- `data/repository_governance/document_system/landing_ack.schema.json`
- `devtools/document_patch_landing.py`
- `devtools/tests/test_document_patch_landing.py`
- `docs/governance/document-system/REAL_REPOSITORY_LANDING.md`

入口：

```bash
.venv/bin/python devtools/docctl.py landing -- --help
.venv/bin/python devtools/document_patch_landing.py --help
```

规划目录必须位于仓库外，并必须提供供应快照根目录。真实仓库尚未安装 landing runner 时，从补丁包解压目录直接运行 runner，并显式传入 protocol 与两份 schema。基础层提交后先运行 `confirm-base`，再安装并提交适配层；未知漂移阻断，已知漂移按 `<date>/<landing-id>` 保存落地时点原字节，再完成 ACK 和密封 successor 安装。工具不会执行 staging、commit、reset、clean 或 amend。
