# Prod-scale Spike — Rollback-safety design

**Slant**: rollback-safety. Spike 几天到几周投入, fail 不 cheap, **核心问题不是
"怎么让 spike 成功", 是"spike 失败时怎么不毁掉项目主线"**.

**Context**: GPT pro audit Finding 5 (2026-05-25, AUDIT_REPORT.md §5)
catch mini Step 8 spike = 50 BoolVar toy + API sanity check, 不足以支撑 prod
"integration path clear". Phase 1.3A 进入前必须有 prod-shaped spike 复测.

**已 land 状态** (2026-05-26 base = master `035bd21`):
- Phase 1.2 NOT GO 后 3 commit patch land: `68fa7f0` (F7/F8 validator bind
  pose registry) + `a3414ee` (7 oracle source_digest fallback drop) + `035bd21`
  (audit archive + lifecycle line-ref fix)
- 主线 framework 完整: 9 family + cut_lifecycle v3.2.2 + state_machine_v2 +
  cut store + replay + assumptions/helpers
- `data/cuts/` 空 (Phase 1.2 设计期, cut store 未启动 production write)

---

## 0. 一句话框架

Spike 必须**branch-isolated + commit-checkpointed + state-sandboxed**, 失败时
`git branch -D` 就干净走人, 主线 zero touch; 成功时 PR 体面 review 进 P1.3A
实施. Worst case 投资是几天的 wall clock, 不是几天 + 主线污染清理.

---

## 1. Spike branch 策略

### 1.1 推荐: long-lived feature branch (NOT master)

```
master (035bd21, Phase 1.2 close base)
  └── spike/prod_scale_master_integration_20260526
        ├── checkpoint commit 1 (fixture builder)
        ├── checkpoint commit 2 (translator)
        ├── checkpoint commit 3 (microbench harness)
        ├── checkpoint commit 4 (real-cut replay)
        └── checkpoint commit 5 (GO/NOT-GO verdict)
```

**为啥不在 master**:
- mini Step 8 spike (`docs/research/p1_2b_mini_step_8_spike_20260525/`)
  本身落在 master 上, 是 50 BoolVar toy + verdict.md, audit 已揭它过 weak.
  prod spike 失败若也 land master, 同样污染 — 不是源代码污染, 是 narrative
  /verdict 污染 (后人 grep 看到的"已 close"档案不可信).
- branch 失败 `git branch -D spike/...` 完全消失, 不留 archeological debris.
- branch 成功 squash merge or rebase-then-merge, master log 只有 1-2 commit
  "feat(P1.3A): prod-scale spike GO + integration baseline".

### 1.2 Per-phase commit 不 squash (spike 阶段)

理由: spike 跑到中间某 design choice 错 (e.g. fixture 用 random cut → 应该
用 oracle 真生成 cut), 要 partial rollback (§3) 时必须能 cherry-pick / revert
单个 checkpoint commit. squash 后失去这个粒度.

每个 checkpoint commit 必含 (commit message 模板):
```
spike(prod-scale): <phase name>

[ROLLBACK-SAFE] this commit is checkpoint-only, not production.
  - branch: spike/prod_scale_master_integration_20260526
  - revert isolation: `git revert <SHA>` clean; no master dependency
  - state-write: <none | data/cuts/spike/* | .artifacts/spike/* >
  - GO/NO-GO so far: <interim signal>
```

### 1.3 失败时 isolation 步骤 (deterministic)

```bash
# Spike abort 标准操作 (assume current branch = spike/...)
git checkout master                                # 跳离 spike branch
git branch -D spike/prod_scale_master_integration_20260526  # 删 branch
rm -rf data/cuts/spike/                            # 清 sandbox state (§4)
rm -rf .artifacts/spike/                           # 清 sandbox artifact
rm -rf docs/research/prod_scale_spike_20260526/    # spike doc 留还是删?
# 留: 失败 verdict.md 作为 lever 死路 archive, 同 lever24/lever25/lever26
# 删: 若 spike 没跑到产 verdict 就 abort (e.g. 第 2 day fixture builder 撞墙)
```

### 1.4 反例: 不要做的

- **不要 in-place master commit + 失败时 revert series**: revert commit chain
  reviewer 噪音大 + git bisect 时 cherry-pick 污染历史. branch delete 干净.
- **不要 worktree-agent-* style 长时间 detached**: 工作树 zombie 风险 + 跟
  master 反复 rebase 痛苦. plain branch 够用.

---

## 2. Abort criteria 量化 (rollback-safety 视角)

abort criteria 不只是"GO/NOT-GO verdict", 还包括"投资到这个阶段还没出
signal 就 abort". 防止 sunk-cost fallacy 让 spike 拖到 1-2 周.

### 2.1 时间盒 (wall clock)

| 阶段 | 累计 wall clock 上限 | 触发 abort 条件 |
|---|---|---|
| Phase 0: fixture 建立 | 4h | prod-scale pose registry / cut body distribution mock 跑不通 → spike 假设错, abort |
| Phase 1: translator + 100 cut microbench | 1 day | build wall > 5s (50× toy 数 = 5.7s threshold), 或 RSS > 8 GB → 集成路径 high risk, **不立刻 abort 但 raise flag**, 继续 Phase 2 看 plateau |
| Phase 2: 1K / 10K active cut microbench | 2 day | build wall > 30s 或 RSS > 16 GB → audit 5.3-5.5 表"测 build wall + ByteSize + RSS" 已落, signal 红, **prepare abort decision** |
| Phase 3: real-cut replay (oracle 真生成) | 3 day | replay 失败 (cut 生成不出来 / scope digest 不对齐 / quarantine 率 > 5%) → integration 端 broken, **立刻 abort** |
| Phase 4: full LBBD 1 candidate end-to-end | 5 day | master wall > 60s per iter (B1 baseline ~52s OPTIMAL, 50% 退化阈值) → 跟 P1.3A plan §1 GO criteria 一致, abort |
| **wall clock 硬上限** | **7 day** | 任何阶段没结论硬 abort, 不论 sunk cost |

### 2.2 量化 NOT GO 数字 (任意一项触发即 abort)

- Build wall > 30s/iter @ 10K active cuts (P1.3A plan §1 spike GO 标准)
- RSS > 30 GB @ prod-scale (撞 §13 路线 master peak baseline + 47 GB cap)
- Replay quarantine 率 > 5% (FP=0 不破但 integration smoke 信号)
- Scope digest drift: oracle 生成 cut → step_6 attach quarantine 率 > 1%
  (Finding 3 修了, 但 prod-scale 真跑要复测)
- master solve UNKNOWN 率 > 30% (B1 baseline ~10%, 3× 退化)
- F8 generator wall > 5s/cut (Finding 4 缓解后阈值)

### 2.3 量化 GO 数字

- Build wall ≤ 30s @ 10K active cuts AND
- Solve wall ≤ 60s/iter (50% 退化 P1.3A plan §1) AND
- RSS ≤ 25 GB (留 22 GB headroom 给 worker scaling) AND
- 真 LBBD candidate end-to-end PASS (跟 Phase 1.2 patch 后 9 family 都 emit
  ≥ 1 cut) AND
- 0 quarantine OR quarantine 率 ≤ 0.1% (近 FP=0 invariant) AND
- ByteSize 增长 < 2× toy 线性外推 (无 hidden non-linear blow up)

---

## 3. Partial rollback boundary

spike 跑到某 design choice 错时, 怎么界定"只回滚那部分" vs "整 spike abort".

### 3.1 Partial rollback OK 的场景 (cherry-pick / revert 单 commit)

- **Fixture builder 错** (Phase 0 commit): 改成不同 mock 方式 (e.g. random
  pose → 真 candidate_placements subset), 重写就行, translator/microbench 复用
- **Translator 某 family 错** (Phase 1 commit): F7 multiset cardinality 算错,
  只 revert F7 translator 那 commit, 不影响其余 5 family
- **Microbench harness 错** (Phase 2 commit): psutil RSS 读法错 / 时钟 measure
  drift, 修 measure 工具不动 fixture / translator
- **某个 family 在 prod-scale 不 scale** (Phase 3 commit): e.g. F8 generator
  撞 Finding 4 复发, 不是整 spike 失败, 只 mark F8 进 Phase 1.5+ defer 列表,
  其余 5 family 继续 Phase 1.3A GO

### 3.2 整 spike abort 的场景 (branch delete)

- **架构层错** (Phase 1 末才发现): translator 全路径都需要 slot-indexed
  master var, 不是 pose-aggregated → spike 设计假设错根, 5 family 全推倒,
  整 branch delete + 重新设计 (回 §1 重起 branch)
- **集成层错** (Phase 4 末): master OPTIMAL 但 binding subproblem 拒绝
  master 选 pose (B1 Phase 6 path-1 同种死法), cut 框架本身 sound 但跟现有
  LBBD pipeline 不互操作 → spike 不能 close, 整 abort + paradigm 层 review
- **Audit 复发** (Phase 3): 跑 prod-scale 发现 Finding 1-3 没真修干净, 还有
  FP=0 break → 主线 patch 本身要重审, spike 暂停 + 回 master 加 patch round
  2 + 重起 spike branch

### 3.3 Boundary 判定 rule

简单标准: **能不能在 1 commit 内 revert 修复**?

- 能 → partial rollback
- 不能 (需改 ≥ 2 个 checkpoint commit 或 needs design rethink) → 整 abort

防 over-partial-rollback: 单 spike branch 内 revert 不能超 3 次, 第 4 次说明
spike 假设根错, 走 §3.2 整 abort.

---

## 4. State isolation (产物哪些会污染 production state)

Spike run 会 produces 啥, 哪些必须 sandbox.

### 4.1 Spike 写的 state 清单 (按污染风险)

| Path | 风险层级 | 隔离策略 |
|---|---|---|
| `data/cuts/*.json` (active) | **CRITICAL** — PROJECT_LOCK §2B 标记的 certified source-of-truth | **绝对禁写**. spike 用 `data/cuts/spike/` 子目录 |
| `data/cuts/quarantine/*.json` | CRITICAL — 同上 | 同上, 写 `data/cuts/spike/quarantine/` |
| `data/checkpoints/*` | CRITICAL — campaign resume state | spike 不跑真 campaign, 不写; 若需 long-run smoke 写 `data/checkpoints/spike/` |
| `data/solutions/*` | CRITICAL — postprocess 但 PROJECT_LOCK §2 锁 | spike 不应产生 final_solution 等; 若需 dummy 写 `.artifacts/spike/solutions/` |
| `data/preprocessed/*` | **FORBIDDEN** — canonical truth | spike 只读, **永禁写**. 若需 mutated registry 用 `data/preprocessed/spike_fixture/` 拷贝 |
| `rules/canonical_rules.json` | **FORBIDDEN** — PROJECT_LOCK §2 头号 | spike 只读, **永禁写**. 任何修改要走 PROJECT_LOCK gate (不是 spike scope) |
| `docs/项目说明/*` | HIGH — 项目 spec | spike 不动 spec, 改了等于 spike 改主线 — 走 §5 off-limits |
| `docs/research/prod_scale_spike_20260526/*` | LOW — spike 自己 artifact | 自由写, 是 spike 自己的 home |
| `.artifacts/spike/*` | LOW — 跑 telemetry | 自由写, 是 sandbox |
| `src/cuts/lifecycle.py` 等 src | HIGH — 主线 framework | spike branch 内可改, 但 §5 enforce 只能改特定 hook 函数 |

### 4.2 隔离机制 (env-gated)

引入 spike-mode env flag:
```bash
EXACT_SPIKE_MODE=1                     # spike pipeline 开关
EXACT_SPIKE_OUTPUT_DIR=data/cuts/spike # 强制 cut store 写 sandbox
EXACT_SPIKE_PROFILE_PATH=.artifacts/spike/profile_$(date +%s).jsonl
```

Cut store / checkpoint writer 必须 honor `EXACT_SPIKE_OUTPUT_DIR`, fall back
default = `data/cuts/` (即 spike mode off 时行为 zero diff). 这跟 §1.2 的
[ROLLBACK-SAFE] commit message 标注是冗余保护 — env 没开就跟 production
完全一致.

### 4.3 跑 spike 前的 baseline snapshot

```bash
# spike 启动前 baseline (用于结束时 diff 验证 state 不漏污染)
git status --porcelain > /tmp/spike_pre_status.txt
find data/cuts/ data/checkpoints/ data/solutions/ data/preprocessed/ \
     rules/canonical_rules.json -type f -exec sha256sum {} \; \
     | sort > /tmp/spike_pre_hashes.txt

# spike 完事后 diff
find data/cuts/ data/checkpoints/ data/solutions/ data/preprocessed/ \
     rules/canonical_rules.json -type f -exec sha256sum {} \; \
     | sort > /tmp/spike_post_hashes.txt
diff /tmp/spike_pre_hashes.txt /tmp/spike_post_hashes.txt
# 必须 empty (除 spike sandbox path), 否则 isolation 破了
```

---

## 5. Project main line 保护 (spike off-limits 列表)

Spike branch 内可改 src, 但有硬 off-limits — 改了等于 spike 在改主线, 失败
时 branch delete 也救不回 (rebase conflict). 这些是 spike PR rebase 时必须
zero diff 的 file/dir.

### 5.1 Hard off-limits (spike 改了等于改主线 → ABORT 信号)

- `PROJECT_LOCK.md` — invariant 锁
- `rules/canonical_rules.json` — canonical truth
- `data/preprocessed/*` — preprocess fixed point
- `src/cuts/lifecycle.py` 中的 §3A 锁的 invariant 函数 (specifically
  `compute_source_digest`, `step_6_attach_scope_check`, `_FAMILY_MODE_MAP`
  dispatch)
- `src/cuts/families/*.py` 的 validator entry function (audit Finding 1/2
  刚修, spike 不能再改, 否则等于 second patch round)
- `src/cuts/assumptions/*.py` — assumption layer 是 cut soundness 根
- 9 个 cut family spec doc (`docs/research/p3_b_design_v2_20260521/
  cut_family_specs/{01-09}*`)
- `docs/项目说明/{01-21}_*.md` — 项目 spec
- `CLAUDE.md` — runbook + invariant

### 5.2 Soft off-limits (改了可以, 但要在 spike PR review 时 flag)

- `src/cuts/lifecycle.py` 其它函数 (e.g. step_8_apply_to_master 占位
  NotImplementedError 是 spike 该填的, OK 改; 但 cycle 内其它 step 函数若
  改了要 justify)
- `src/cuts/oracles/*` — oracle 生成器, spike 测可能要加 telemetry hook,
  但 telemetry 必须 env-gated, default-off 时 zero behavior diff

### 5.3 Spike PR rebase 验证

```bash
# Spike branch ready merge 前必跑
git checkout master
git checkout -b spike-rebase-test
git merge --no-commit --no-ff spike/prod_scale_master_integration_20260526
git diff --cached --name-only > /tmp/spike_diff_files.txt

# off-limits 文件不能出现
for offlimits in "PROJECT_LOCK.md" "rules/canonical_rules.json" \
                 "data/preprocessed/" "docs/项目说明/" "CLAUDE.md"; do
    if grep -q "^$offlimits" /tmp/spike_diff_files.txt; then
        echo "SPIKE PR BLOCKED: off-limits file changed: $offlimits"
        exit 1
    fi
done
```

---

## 6. Spike 成功后 graceful land

假设 spike GO, 怎么把 spike code 干净接入 P1.3A 真实施.

### 6.1 决策: spike code = throwaway OR stepping stone?

**默认 throwaway** (rollback-safety 偏向). 理由:
- Spike fixture 是 mock + microbench harness, prod 不需要
- spike translator 是 hand-rolled toy, prod 真要的是 `step_8_apply_to_master`
  全 wire + benders_loop hook + active cut filter + rotation policy + telemetry
- spike code review 标准 < production review 标准 (commit message 标
  [ROLLBACK-SAFE]), prod 进 master 标准必须按 master commit gate

**例外 stepping stone 允许的部分** (spike 可 cherry-pick 进 P1.3A 实施 PR):
- Microbench harness (`scripts/microbench_prod_scale.py`) — verify
  regression 持续用
- Family→CP-SAT translator 的核心映射逻辑 (mini Step 8 verdict 表已识别
  5 form), 但需重写成 production quality (type hint / docstring / test)
- Telemetry hook (env-gated profile dump) — Phase 1.3B 持续要

### 6.2 Land 流程

```
spike branch verdict = GO
  ↓
PR #1: 把 spike artifact 进 master (doc only)
  - docs/research/prod_scale_spike_20260526/verdict.md (GO)
  - docs/research/prod_scale_spike_20260526/microbench_data.json
  - scripts/microbench_prod_scale.py (持续 regression tool)
  - 不进任何 src/ 改动
  ↓
PR #2: P1.3A step_8_apply_to_master production 实施
  - 不 cherry-pick spike branch, 重写
  - reference spike verdict + microbench data 作 GO justification
  - 走完整 review (Gemini cross-check + 必要时 GPT pro batch review)
  ↓
spike branch close: delete or archive
  - 推荐 delete (rollback-safety: archive branch 是死代码, 永远在 grep 噪音里)
  - 必要 archive 用 tag: `git tag spike-archive/prod_scale_20260526 <SHA>`
    然后 delete branch — tag 比 branch 干净, 不在 `git branch` 默认列表
```

### 6.3 防 spike → prod 隐性碾压

Spike "看起来 GO" → 直接 cherry-pick spike code 进 master = 反 pattern. 历史
教训:
- mini Step 8 spike: 50 BoolVar toy 看起来 GO → verdict.md land master → audit
  揭实际不是 prod 信号 (Finding 5)
- B1 Phase 0 GO → 直接 land production → Phase 6 才发现 master.solve scale 死
- v8 anchor slicing: GPT patch clean apply + 2211 pytest pass → 实测 5 min
  UNKNOWN 死路 (project_v8_anchor_slicing_dead)

防法: **spike GO 不是 prod GO**. spike GO 只解锁 "可以投资 P1.3A 实施", 不是
"可以把 spike code 直接 land". 这条写进 PR #1 description 显式.

---

## 7. Audit / revert capability

任何步骤 `git revert <SHA>` 或 `git reset --hard <SHA>` 必须干净复原.

### 7.1 Checkpoint 频率

| 工作量 | checkpoint | rationale |
|---|---|---|
| Fixture builder (200-500 LOC) | 1 commit | 单独一个 commit, scope clean |
| Translator per family (50-100 LOC × 9) | 1 commit / 2-3 family | 每 commit 含 1-3 family translator + 1-2 test, 失败时 revert 单 family 不影响其它 |
| Microbench harness (100-200 LOC) | 1 commit | 独立 commit, 跟 fixture decoupled |
| End-to-end LBBD smoke (50 LOC wrap) | 1 commit | 失败时 revert smoke 不动 microbench |
| Verdict + data | 1 commit | docs only |

总: ~7-10 commit. 不要 ≤ 3 commit (粒度太粗, revert 拿不回去), 不要 ≥ 20
commit (review 噪音, 找问题难).

### 7.2 Revert 路径

```bash
# Case A: spike branch 中某 commit 错, 还在 spike branch
git revert <bad_commit_SHA>          # 新 commit revert, 保留历史
# 或
git reset --hard <good_commit_SHA>   # 抹掉 bad commit 后所有

# Case B: spike 已 abort, branch deleted, 但发现 PR #1 verdict.md 已 land
#         master 而 spike 实际是死路
git revert <verdict_commit_SHA_on_master>  # master 上新 commit revert verdict
# 同步更新 docs/项目说明/06_current_status.md 记 "spike rolled back"

# Case C: 极端 — PR #2 production 实施 land 后发现 spike 实际不能 prod-scale
#         (e.g. 168h campaign 跑出来撞 30 GB RSS)
git revert <prod_impl_commit_SHA>    # production 退回, env flag default off
# 同步 readiness_gate 加 hard block, 防止再启用
```

### 7.3 强制约束 (写进 spike branch CLAUDE.md addendum)

- 每 commit 不能跨 ≥ 5 个 src 文件 (revert atomicity)
- 每 commit 必有对应 test 或 microbench data (失败时 binary signal 清晰)
- 不允许 force push spike branch (rollback 信任 git log)
- spike branch 不能 merge 进 master, 只能 cherry-pick (§6.2)

---

## 8. 量化 GO criteria (rollback 视角)

从"GO 后能 graceful land 不毁主线"角度补充 §2.3.

GO 必须**同时**满足以下 (rollback 视角):

1. **Technical GO** (§2.3 全部数字达标)
2. **State isolation 验证** (§4.3 baseline diff empty 除 sandbox)
3. **Off-limits clean** (§5.3 spike PR 无 off-limits file 改动)
4. **Reproducibility**: microbench data 跑 ≥ 3 次 (different seed)
   variance < 10% (不是单次幸运数字)
5. **Reviewer 复现** (Gemini cross-check): spike branch checkout + run
   harness 跑出来 GO/NOT-GO 一致 (跟历史 GPT review reproducibility 警告
   配套, feedback_external_review_reproducibility)
6. **Audit trail 完整**: spike 7-10 commit log 清晰, 每 commit message 标
   [ROLLBACK-SAFE] + GO/NOT-GO interim signal, 后人能 git bisect

---

## 9. 量化 NOT GO criteria (rollback 视角)

NOT GO 不止是数字红, 还包括"即使数字绿也不该 land"的 rollback-fail 条件:

1. **Technical NOT GO** (§2.2 任意数字红)
2. **State leak**: §4.3 diff 显示 spike 写了 sandbox 外文件 → isolation 破,
   不论 GO/NOT-GO 都 abort + 不 land (体系 broken)
3. **Off-limits violation**: §5.3 PR 含 off-limits diff → abort + branch
   delete + 重起
4. **Wall clock 超 7 day** (§2.1 硬上限) — 不论进度
5. **Reproducibility 失败**: microbench 3 次 variance > 30% → 数字不可信
6. **Reviewer 复现失败**: Gemini cross-check 跑出来不一致 → finding 不真,
   不能 land
7. **Audit Finding 复发**: prod-scale 真跑揭示 Finding 1-3 patch 不够 →
   暂停 spike 回 master 补 patch round 2 (Phase 1.2 重新 close), spike 重起
8. **Sunk-cost reject**: spike 跑到第 5 day signal 是 yellow (build wall
   18s, threshold 30s 但跟 toy 外推差 3×) → 选项不是"继续投资到 7 day
   看是否能优化到 5s", 是 "land NOT GO + 把 yellow 作 P1.3A 进入 risk
   register"

---

## 10. 工时估 (Claude pace)

按全局 CLAUDE.md "工时按 Claude 节奏估" 段, 不打人类 buffer.

| 阶段 | Claude wall clock | 真死时间 |
|---|---|---|
| Phase 0: fixture builder | 2-3h | 0 (跑 fixture 是几秒) |
| Phase 1: translator + 100 cut microbench | 4-6h | 0 |
| Phase 2: 1K / 10K microbench harness + run | 1 day | 跑 ~10 min |
| Phase 3: real-cut replay (oracle 真生成) | 1 day | 跑 ~30 min |
| Phase 4: full LBBD 1 candidate end-to-end | 1-2 day | 跑 ~1-2h per candidate |
| Phase 5: verdict + data + PR | 4-6h | 0 |
| **合计 Claude wall** | **~4-5 day** | ~2-3h 死时间 |

7 day 硬上限 (§2.1) 留 ~30-40% buffer 容 partial rollback (§3) 或 architecture
重设. 不再 buffer.

跟 mini Step 8 spike (实际几小时) 对比 prod spike 30-50× 量级是合理的, 因为:
- fixture 从 50 BoolVar toy → 266 instance × ~280K pose 真规模
- microbench 维度从 "build wall + solve wall" → "+ RSS + ByteSize + replay
  quarantine 率 + LBBD smoke"
- real cut 而不是 random — oracle 生成 + scope digest + assumption resolve
  全要走

---

## 11. 我 rollback-safety slant 偏向 — 自承可能 over-emphasize defensive

我倾向 worst-case scenario 设计, 这本身有几个 bias 需要别 slant compensate:

### 11.1 Over-defensive 风险

- **branch isolation 可能 over-cautious**: 如果项目其它人 / 后续 Claude
  agent 大概率不会在 spike 7-day window 内有 conflict commit, in-place
  master 反而省一次 rebase / cherry-pick 操作. simplicity / throughput slant
  可能更对 — branch overhead vs context switch cost trade-off 我没量
- **Off-limits 列表可能太长**: §5.1 写 8 项, 实际 spike 可能只动 1-2 项.
  长 list = 多个 false-block 风险, reviewer 烦
- **Checkpoint 频率推 7-10 commit**: throughput slant 可能推 squash 3 commit
  + 失败时 force-push rewrite history. 后者更激进但 spike branch isolation
  下也安全 — 我偏向 "保留历史" 是 audit trail bias

### 11.2 Progress velocity 牺牲

- §2.1 wall clock 7 day 硬上限 + §3 partial rollback rule + §4 state diff
  验证, 每条都加 ~10-20% overhead. 累积下来 spike "纯进度" 可能从理论 3 day
  变 5 day
- §6.2 strict 2-PR 流程 (verdict PR + 实施 PR) 比 1-PR 慢. simplicity slant
  可能推 1-PR 直接 land + 失败时 revert — risk-reward 我没算赢
- §11.1 + §11.2 综合: 我 design 适合 "spike 失败概率 > 30%" 场景. 如果其它
  slant 论证 spike 失败概率 < 10% (例如 mini Step 8 已 verify CP-SAT API 形
  状 OK, 真规模问题主要是 RSS 量), 我的 defensive 部分应该 relax

### 11.3 怎么决定要不要听我

- spike 失败赔率高 (e.g. prod RSS 不确定性大) → 听 rollback-safety
- spike 失败赔率低 (大部分 risk 已被 mini Step 8 拍掉) → 听 throughput /
  simplicity, 我只做关键 §4 state isolation + §5 off-limits 这两段, 其它放松

---

## 12. 潜在 blind spot

我作为 rollback-safety slant 自己看不到 / 容易漏的:

1. **不会 catch "spike 设计的 metric 本身是错的"**: 我专注怎么 abort /
   rollback, 但如果 spike measure "build wall < 30s" 这个 threshold 本身就
   不是 prod 真瓶颈 (真瓶颈是 hot path evaluate frequency × call cost), abort
   criteria 数字再严也没用. 这需要 correctness-paranoid / adversarial slant
2. **不会 catch paradigm 层"spike 根本不该做"**: 如果 prod-scale spike 是
   wrong question (真问题是 master OPTIMAL 后 binding 拒绝, 跟 cut framework
   无关), 我整套 rollback-safety 都白做. 这需要回去看 27 lever 死亡史 /
   B1 Phase 6 path-1/path-2 死路 (audit slant 看)
3. **不会 catch 隐性 prod 状态污染**: 我列了 data/cuts/ data/checkpoints/
   等显式 path, 但 prod 可能有隐性状态 (e.g. Python lru_cache pickle 文件 /
   tempfile 残留 / 系统 page cache 影响 CP-SAT presolve seed), 这些我看不到
4. **不会 catch human review fatigue**: 7-10 commit + 2 PR + Gemini cross-
   check 每一步都加审查, 真审查质量随次数衰减. simplicity slant 可能更对
5. **不会量化 "rollback 本身的成本"**: branch delete 简单, 但 spike 已经
   sunk 7 day Claude wall + reviewer 反复 cross-check + 用户耐心 — 这些不在
   git history 里, 我 §1.3 一句话 `git branch -D` 太轻
6. **不会 catch 跟其它 slant 设计冲突**: 比如 adversarial slant 推"在 master
   in-place commit 故意诱发 conflict 验证 isolation", 我推 "branch 隔离防
   conflict", 两个直接对立. main agent 要 merge 时我没有 framework 告诉怎么
   选

---

## 13. 跟其它 4 slant 的合点

| Slant | 跟我对齐 | 跟我冲突 | merge 建议 |
|---|---|---|---|
| correctness-paranoid | §4 state isolation + §5 off-limits 高度对齐 (都防污染) | 可能推更多 invariant check 进 spike, 拖时间 — 跟我 §2.1 wall clock 冲突 | 取我 isolation + 它 invariant check, 用 env-gated default-on 防 spike 跳过 |
| throughput | §6 graceful land 流程对齐 (都想干净 ship) | 推 in-place master commit + squash, 跟我 §1 branch 推荐冲突 | 用 spike 失败概率作 tie-breaker (§11.3) |
| adversarial-schema | §2 abort criteria 对齐 (都量化) | 可能推主动注入 schema corruption 验 isolation, 跟我 §4 baseline diff 测被动检测互补 | 两者都做, adversarial 测脚本作 §4.3 baseline diff 的 enrichment |
| simplicity | 都推 throwaway spike code (§6.1) | 推 ≤ 3 commit, 跟我 7-10 commit 冲突 | 量化: spike 总 LOC < 500 用 simplicity 3 commit; > 500 用我 7-10 commit |

---

## 附: Spike abort decision cheat sheet

```
trigger condition                            → action
-----------------------------------------------------
wall clock > 7 day                           → ABORT (branch delete)
build wall > 30s @ 10K cuts                  → ABORT
RSS > 30 GB @ prod-scale                     → ABORT
master solve wall > 60s/iter                 → ABORT
quarantine 率 > 5%                          → ABORT (audit Finding 复发)
scope digest drift > 1%                      → ABORT (Finding 3 复发)
off-limits file 改动 (§5.1)                  → ABORT (体系破)
state leak (sandbox 外文件 mutated)          → ABORT (isolation 破)
reproducibility variance > 30%               → ABORT (数字不可信)
Gemini cross-check 不一致                    → ABORT (finding 不真)

单 commit revert 修复 ≤ 3 次                 → PARTIAL ROLLBACK (continue)
单 commit revert 修复 > 3 次                 → ABORT (假设错根)
single family translator 错                  → PARTIAL (revert 该 family)
microbench harness 错                        → PARTIAL (revert harness)
fixture builder 错                           → PARTIAL (Phase 0 重做)
architecture 层错 (slot vs pose-aggregated)  → ABORT (design rethink)
integration 层错 (binding 拒 master pose)    → ABORT (paradigm review)

绿全部 → land 流程 §6.2
  ├── PR #1 verdict + microbench + tool (doc only)
  ├── PR #2 production 实施 (重写, 不 cherry-pick)
  └── spike branch tag-then-delete
```
