# 真实仓库非破坏性落地指南

状态：CURRENT
适用系统版本：`2.6.0`
机器协议：`data/repository_governance/document_system/landing.json`
执行器：`devtools/document_patch_landing.py`

## 1. 为什么不能直接套累计补丁

供应快照与真实共享工作区并不拥有相同的 Git 拓扑。真实仓库可能同时包含 Git-tracked 文件、多个 agent 共同维护的 untracked workspace overlay、仓外 evidence，以及快照后仍在追加 owner 记录或维护欠账的旧页面。

因此，`git apply --check` 的冲突清单不是固定排除表。每次落地都必须重新测量，并把三种情况一起视为漂移：

```text
补丁 hunk 冲突
补丁目标是现存的 untracked 文件
当前字节虽不冲突，但已经偏离供应基线
```

任何未登记漂移都会阻断，而不是被静默覆盖。

## 2. 安全边界

落地执行器不会调用，也不得由包装脚本调用：

```text
git reset --hard
git clean
git add -A
git commit
git commit --amend
```

它要求专用具名分支和 clean index，但允许协议已登记的旧页以规划时的精确字节保持 dirty。分支创建、精确 staging、commit 和语义内容确认始终由操作者完成。

协议、schema、ACK schema 和执行器属于 framework core。真实仓库尚未安装适配层时，规划必须使用补丁包中的 bootstrap 副本，不能假设目标仓库已经拥有这些文件。

## 3. 六步落地事务

### 3.1 在仓外创建密封计划

先准备三个输入：

```text
真实仓库工作树
累计基础补丁
该补丁所针对的供应基线目录
```

使用补丁包中的 bootstrap 执行器和协议：

```bash
PYTHON=/absolute/path/to/python3.13
BOOTSTRAP=/absolute/path/to/batch4/landing_bootstrap
PLAN_DIR=/absolute/path/outside/repository/landing-plan

"$PYTHON" "$BOOTSTRAP/document_patch_landing.py" plan \
  --repo-root "$PWD" \
  --patch /absolute/path/to/cumulative-base.patch \
  --baseline-root /absolute/path/to/supplier-baseline \
  --protocol "$BOOTSTRAP/landing.json" \
  --protocol-schema "$BOOTSTRAP/landing.schema.json" \
  --ack-schema "$BOOTSTRAP/landing_ack.schema.json" \
  --output "$PLAN_DIR" \
  --landing-id phase4-batch4-real-landing
```

规划器会复制并密封补丁和协议 bundle，逐路径比较真实字节与供应基线，保存漂移源原字节、diff、SHA-256，并从“供应基线 + 累计补丁”推导 package-owned successor。`LANDING_PLAN.json`、`BASELINE_PATHS.json` 及其 `.sha256` 不得手工修改。

计划状态为 `BLOCKED` 时停止。先为新漂移补迁移合同、测试和适配设计，再重新规划。

### 3.2 应用并立即提交基础层

```bash
"$PYTHON" "$BOOTSTRAP/document_patch_landing.py" apply-base \
  --repo-root "$PWD" \
  --plan "$PLAN_DIR/LANDING_PLAN.json"
```

命令会重验 Git-visible 指纹、全部 patch target 字节、动态冲突集合和漂移快照。它只应用 `BASE_APPLY_PATHS.nul` 中的路径，不做回滚。

随后使用精确 NUL pathspec staging：

```bash
git add --pathspec-from-file="$PLAN_DIR/BASE_APPLY_PATHS.nul" --pathspec-file-nul
git diff --cached --name-only
git commit -m 'apply cumulative document base layer'
```

不要夹带任何额外路径。提交后立即确认：

```bash
"$PYTHON" "$BOOTSTRAP/document_patch_landing.py" confirm-base \
  --repo-root "$PWD" \
  --plan "$PLAN_DIR/LANDING_PLAN.json"
```

`confirm-base` 要求规划时 HEAD 之后恰好有一个基础提交，提交路径集合和提交字节均与 apply receipt 精确一致。

### 3.3 安装并提交 Batch 4 适配层

此时应用 Phase 4 Batch 4 的适配补丁，按补丁包给出的精确 pathspec 提交。不能把 `CLAUDE.md`、`AGENTS.md` 或本机 `.artifacts/**` 用 `git add -A` 灌入 Git。

后续命令会验证目标仓库中三份 landing 协议文件均为 Git-tracked、已提交，并与规划 bundle 字节一致。只复制文件而不提交不会通过。

### 3.4 开启落地时迁移

```bash
"$PYTHON" "$BOOTSTRAP/document_patch_landing.py" begin-migration \
  --repo-root "$PWD" \
  --plan "$PLAN_DIR/LANDING_PLAN.json" \
  --landing-date 2026-08-14
```

该命令在任何仓内写入前完成预检，然后：

- 将每份漂移文件的落地时原字节归档到 `docs/history/status/landing/<date>/<landing-id>/...`；
- 写入同目录的 `LANDING_ARCHIVE_MANIFEST.json`；
- 在仓外保存所有可能迁移目标的前置字节；
- 密封 `MIGRATION_STATE.json`；
- 生成可填写的 `MIGRATION_ACK.json`。

归档保存“落地时真实存在过什么”，不是当前状态页。归档路径包含 landing ID，避免同一天多次落地互相覆盖。

### 3.5 完成语义迁移并预核验

按 ACK 中的 obligation 写入当前承载面：

- 旧 roadmap 中的 owner 登记进入非授权、append-only 的 `data/knowledge/decisions.jsonl`，并进入 `docs/项目说明/HISTORY.md`；
- 旧 dashboard 中的 A12/A13 进入当前欠账承载面；
- `docs/AGENT_OPERATIONS.md` 吸收耐久操作知识；
- untracked `CLAUDE.md` 保留轻量自举、空白重建历史和 workspace overlay 自指提醒。

`required_strings` 必须是归档源中实际出现的、足以定位迁移语义的字符串。对 JSONL 目标，record ID、archive path、源 SHA-256 和这些字符串必须共存于同一条指定记录，不能散落在文件其他行中。

预核验：

```bash
"$PYTHON" "$BOOTSTRAP/document_patch_landing.py" verify-migration \
  --repo-root "$PWD" \
  --plan "$PLAN_DIR/LANDING_PLAN.json" \
  --ack "$PLAN_DIR/MIGRATION_ACK.json"
```

核验会检查 byte-faithful archive、append-only 前缀、ACK schema、target format、记录级坐标、overlay 调和标记，以及 package successor 尚未提前覆盖旧页。

### 3.6 安装密封 successor 并提交迁移层

```bash
"$PYTHON" "$BOOTSTRAP/document_patch_landing.py" finalize-migration \
  --repo-root "$PWD" \
  --plan "$PLAN_DIR/LANDING_PLAN.json" \
  --ack "$PLAN_DIR/MIGRATION_ACK.json"
```

successor 不再来自操作者指定的外部目录，而是规划阶段由供应基线和原累计补丁推导、密封在计划中的字节。这样可以避免把任意“看起来像新页面”的文件当成规范 successor。

finalize 会先验证所有 successor，再替换 package-owned 旧页；若中途已写入部分精确 successor，重复执行可以继续，任何第三种字节形态都会阻断。`CLAUDE.md` 属于 `manual_overlay`，不会被 package successor 覆盖。

使用生成的精确列表提交 tracked 迁移结果：

```bash
git add --pathspec-from-file="$PLAN_DIR/MIGRATION_CHANGED_PATHS.nul" --pathspec-file-nul
git diff --cached --name-only
git commit -m 'migrate landing-time document drift'
```

`WORKSPACE_OVERLAY_PATHS.txt` 只用于提醒，不得据此把 overlay 加入 Git。

## 4. ACK 能证明什么

ACK 与执行器可以机械证明：

- 每个动态漂移源恰好有一条迁移记录；
- 归档字节与规划源完全一致；
- 每个 obligation 使用允许的目标和声明的 `text/json/jsonl` 格式；
- source-derived 字符串确实来自归档源；
- JSONL 中指定记录自身携带 ID、归档路径、源摘要和承重字符串；
- append-only 目标没有改写既有前缀；
- overlay 已调和且保留自举标记；
- package successor 来自密封计划，并在 finalize 前后处于正确状态。

它不能替 owner 判断新 decision 的数学或治理内容是否正确，不能把非授权 decisions register 提升为 owner authority，也不能授予 production/certification authority。

## 5. 最终验收

完成迁移提交后依次执行：

```bash
.venv/bin/python devtools/check_knowledge_docs.py
.venv/bin/python devtools/docctl.py doctor
.venv/bin/python devtools/document_governance_gate.py run --profile changed
.venv/bin/python scripts/preflight_gate.py --full
```

文档治理门检查知识、文档与仓库治理结构是否自洽；production preflight 检查 production/certification 边界。两门互不授予对方 authority，任一阻断都不能宣称整体通过。
