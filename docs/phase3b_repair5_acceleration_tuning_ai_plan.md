# Phase3B Repair5：性能调优 × AI 加速一体化全流程计划表

> ⚠️ **HISTORICAL / SUPERSEDED (2026-06-04)**：整个 Phase 3B tuning paradigm 已被 **cut-family LBBD** 取代（当前 Phase 1.2 spike close，见 `CLAUDE.md`）。本计划本身已是历史（文内 L6 的 "superseded" 仅指更早的 13900KS 单线调优计划，不要误读为本计划仍是当前主线）。

生成日期：2026-04-29  
计划版本：v1.0  
参考项目包：`phase3b_pre_production_full_audit_upload_20260429_repair5_20260429_213207.zip`  
参考调优计划：旧 13900KS HT-off 单线调优计划已被本一体化计划 superseded  
适用机器：Intel Core i9-13900KS，HT-off，`8P + 16E = 24` 可调度硬件线程，DDR5-7600 48GB 级别内存  
计划定位：把“本机性能调优”和“AI/ML 加速探索”合并成一个可执行、可扩展、不会污染 `certified_exact` 的后置实验路线图。

---

## 0. 一句话结论

现在不应该把“性能调优”和“AI 加速”做成两条互相抢入口的路线。

正确做法是：

```text
先建观测与安全底座
  ↓
先做 deterministic/config-only 性能调优，拿到可信 baseline 与 top profiles
  ↓
AI 先只做 shadow/offline 分析：抽特征、回放排序、解释 UNKNOWN
  ↓
AI 通过离线 replay 后，才进入 order-only 非最终 A/B
  ↓
再尝试 CP-SAT hints / local repair / runtime diagnostics 等更深 AI 模块
  ↓
最终候选仍必须 fresh production acceptance + gate revalidation
```

也就是说：

```text
性能调优 = 主干推进线
AI 加速 = 旁路探索线 + 可插拔 sidecar
runtime/IndustrialPlanner 诊断 = 另一个只读诊断 sidecar
```

AI 不能成为 proof source，不能形成正式剪枝，不能写 canonical checkpoint，也不能改变 candidate set。AI 的第一目标不是“直接证明更快”，而是先让调优数据可解释、让 UNKNOWN 可分类、让候选执行顺序更聪明。

---

## 1. 当前最新 Repair5 起点

### 1.1 Repair5 包状态

最新包是：

```text
phase3b_pre_production_full_audit_upload_20260429_repair5_20260429_213207.zip
```

包 metadata 显示当前 Repair5 范围仍是：

```text
scope = gate-security-package-hygiene-only
performance_tuning_in_scope = false
final_168h_started = false
final_168h_authorized = false
execution_allowed = false
runtime_elimination_authorized = false
checkpoint_write_or_import_back_authorized = false
proof_source = false
preflight_gate_mutated = false
release_viewer_frontdoor_status_promoted = false
```

所以本计划必须作为 **post-audit experimental branch/workspace** 执行，不属于 Repair5 当前 audit verdict 本身。

### 1.2 当前默认生产 profile

最新 Repair5 的默认生产入口仍是：

```powershell
scripts/run_prod_4x4_normal.ps1
```

等价核心参数：

```text
python main.py
  --mode certified_exact
  --campaign-hours 168.0
  --parallel-processes 4
  --process-priority normal
  --frontier-probe-mode auto

EXACT_CP_SAT_WORKERS=4
```

也就是：

```text
4 个独立进程 × 每进程全局 CP-SAT workers=4
```

在 HT-off 24 线程机器上，它是 conservative production profile，不是满载 profile。

### 1.3 当前 CP-SAT worker precedence

`src/models/cp_sat_worker_config.py` 当前语义：

```text
1. stage-specific env：
   EXACT_MASTER_CP_SAT_WORKERS
   EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS
   EXACT_BINDING_CP_SAT_WORKERS
   EXACT_ROUTING_CP_SAT_WORKERS

2. global env：
   EXACT_CP_SAT_WORKERS

3. built-in defaults：
   master = 8
   local_capacity = 8
   binding = 4
   routing = 8
```

因为 `run_prod_4x4_normal.ps1` 显式设置 `EXACT_CP_SAT_WORKERS=4`，所以默认生产运行中四个阶段都会解析为 `4`，除非额外设置 stage-specific env。

### 1.4 Repair5 clean extraction 验证状态

最新包的 clean-extraction validation summary 显示：

```text
focused pytest: 159 passed in 7.49s
final preflight ready: True
ready to request human launch authorization: True
final 168h authorized: False
execution allowed: False
non-dry-run command: not emitted without human authorization
final production dry-run: would_start_final_168h=False
Repair5 adversarial B5A marker exists tamper probe: passed
```

这说明调优开始前的安全边界是清楚的：可以请求人工 launch authorization，但本计划不能授权 final 168h，也不能启动 final 168h。

### 1.5 当前 production acceptance baseline 摘要

最新包内 `.codex_test_logs/phase3b/production_acceptance_after_change.json` 有 4 个生产验收式对照 run：

| label | process_count | worker_count_per_process | peak RSS external total | 约 GiB | completed | campaign_valid_after_run |
|---|---:|---:|---:|---:|---|---|
| `prod_1x1` | 1 | 1 | 10,120,019,968 bytes | 9.43 GiB | true | true |
| `prod_2x4` | 2 | 4 | 19,536,551,936 bytes | 18.20 GiB | true | true |
| `prod_4x4` | 4 | 4 | 30,661,275,648 bytes | 28.56 GiB | true | true |
| `prod_2x8` | 2 | 8 | 19,522,797,568 bytes | 18.18 GiB | true | true |

这个表的解释重点：

```text
1. 当前 4x4 有内存压力但还在 48GB 机器可接受范围。
2. 进程数会明显拉高 RSS；5 进程需要谨慎实测，6+ 默认高风险。
3. 2x8 与 2x4 RSS 接近，说明 per-process worker 增加未必显著增加 RSS，但不代表求解推进一定更好。
4. 当前 acceptance 的 CPU/推进 telemetry 不足以直接判断“最优 profile”，因此必须先补 telemetry。
```

---

## 2. 本计划回答的核心问题

用户当前困惑可以拆成四个具体问题：

| 问题 | 本计划的回答 |
|---|---|
| 性能调优和 AI 加速是先做哪个？ | 先做观测底座和 deterministic 调优；AI 先 shadow/offline，不主动影响 certified run。 |
| 是否要把每个部分切分后组合？ | 是。拆成四条 lane：安全/观测主干、性能调优主干、AI sidecar、runtime 诊断 sidecar。按 gate 组合。 |
| 原性能调优计划要不要改？ | 要改，但不是推翻。保留 P0-P12 主体，在 P2/P3/P7/P8/P9/P10/P11 插入 AI 影子、回放、A/B 与合同测试。 |
| AI 方向没完全定，是否还能做全流程计划？ | 可以。计划不锁死具体模型，而锁死“生命周期、门槛、边界、工件、退出条件”。AI 模块用 registry 扩展。 |

---

## 3. 四条 lane 的总架构

```text
Lane A：安全与观测底座
  clean baseline / hardware profile / telemetry / path audit / gate checks

Lane B：deterministic 性能调优主干
  process × workers / stage-specific workers / priority / affinity / memory variants

Lane C：AI 加速 sidecar
  feature extraction / offline replay / candidate ranking / UNKNOWN triage / CP-SAT hints

Lane D：runtime / IndustrialPlanner 诊断 sidecar
  blueprint runtime report / bottleneck timeline / local repair window / non-proof diagnostics
```

合并原则：

```text
A 是所有 lane 的前置条件。
B 是主线，优先产出可稳定复现的 profile。
C 依赖 A 的 telemetry 与 B 的实验数据，前期只能 shadow。
D 与 exact proof 隔离，只允许读 exact 输出或蓝图，写 .artifacts/blueprint-runtime。
```

---

## 4. 总执行顺序

### 4.1 推荐顺序图

```text
S0 当前 Repair5 clean baseline
  ↓
S1 独立 tuning/ai workspace + Python 3.13 环境确认
  ↓
S2 telemetry scaffold + hardware profile + safety path audit
  ↓
S3 prod_4x4_normal baseline reproduction
  ↓
S4 config-only short matrix
  ├─ 同步产出 AI dataset v0，但 AI 不影响 run
  ↓
S5 stage-specific worker matrix
  ├─ 同步做 UNKNOWN triage / candidate feature extraction
  ↓
S6 priority / affinity / P/E core exploratory
  ↓
S7 medium confirmation：筛出 deterministic top profiles
  ├─ AI offline replay：只比较排序收益，不接入 scheduler
  ↓
S8 AI order-only sidecar MVP：shadow → non-final A/B
  ↓
S9 CP-SAT hints / nearest-neighbor warm start：只做非最终局部试验
  ↓
S10 必要时 memory/code variants
  ↓
S11 final candidate freeze：可能是纯 profile，也可能是 profile + AI order-only sidecar
  ↓
S12 fresh production acceptance refresh
  ↓
S13 Repair5 gate revalidation + adversarial negative tests
  ↓
S14 final recommendation：保持默认 / 请求人工评审 profile change / 请求更长非最终确认
```

### 4.2 哪些可以并行，哪些不能并行

| 任务 | 能否并行 | 说明 |
|---|---|---|
| P0 clean baseline 与 P1 hardware profile | 可以轻度并行 | 但 baseline 失败时停止所有调优。 |
| telemetry scaffold 与 tuning runner | 可以并行 | 二者都属于观测/执行工具，不改 proof semantics。 |
| config-only matrix 与 AI feature extraction | 可以并行 | AI 只读 telemetry，不能影响执行顺序。 |
| stage-specific worker 与 AI UNKNOWN triage | 可以并行 | AI 只做分类、解释、离线回放。 |
| AI offline replay 与 medium confirmation | 可以并行 | replay 不写 checkpoint，不改变 run。 |
| AI scheduler A/B 与 final candidate freeze | 不能直接并行 | AI A/B 必须先过合同测试，再进入候选冻结。 |
| fresh production acceptance 与 gate revalidation | 不能跳过 | 所有最终候选必须跑。 |
| final 168h launch | 不属于本计划授权 | 只能由人工另行授权。 |

---

## 5. 对现有性能调优计划的修改建议

旧 13900KS HT-off 单线调优计划的总体方向正确：先 telemetry、再 config-only、再 stage-specific、再 affinity/priority、再中测、再 acceptance/gate。该旧计划已被本一体化计划 superseded；本计划把 AI 加速从“另一个想法”纳入实验生命周期，而不是提前塞进 production profile。

### 5.1 保留不变的部分

| 原计划部分 | 是否保留 | 原因 |
|---|---|---|
| Repair5 不含 performance tuning | 保留 | 这是当前 package metadata 明确边界。 |
| 不授权 final 168h | 保留 | 调优和 AI 不能绕过人工 launch authorization。 |
| tuning workspace 隔离 | 保留 | 防止污染 canonical checkpoint/proof source。 |
| telemetry 优先 | 保留 | AI 与调优都依赖它。 |
| config-only matrix | 保留 | 最低风险、最可解释。 |
| stage-specific workers | 保留并提前 | 当前代码已支持 stage env，是低风险收益点。 |
| affinity/priority exploratory | 保留但降权 | P/E mapping 未确认前不能成为默认依据。 |
| fresh acceptance + gate revalidation | 保留 | 最终候选必须过。 |

### 5.2 需要新增的部分

| 新增章节 | 插入位置 | 内容 |
|---|---|---|
| `AI acceleration safety contract` | 原第 1 节之后 | 明确 AI 不删候选、不写 checkpoint、不生成 proof、不改 hash。 |
| `AI artifact namespace` | 原第 5 节工作区之后 | 新增 `.artifacts/phase3b_ai_accel_*` 与 `.codex_test_logs/phase3b/ai_accel_*`。 |
| `Telemetry fields for AI` | 原第 7 节之后 | 候选特征、run profile、状态标签、UNKNOWN subtype、resource metrics。 |
| `AI shadow dataset v0` | 原 P3/P4 之间 | 从 baseline/matrix 只读生成训练/回放数据。 |
| `Offline replay gate` | 原 P7 后 | AI 必须先在 replay 中证明排序收益与稳定性。 |
| `Order-only scheduler A/B` | 原 P8 前 | AI 只改变候选顺序，不 drop，不 prune。 |
| `CP-SAT hint experiments` | 原 P8 后 | nearest-neighbor / lightweight model hints，非最终。 |
| `AI contract tests` | 原 P11 gate revalidation | 新增测试 AI 不写 canonical paths、不改 candidate set。 |
| `AI module registry` | 原 P12 final deliverables | 允许未来新增模型，但每个模型必须有生命周期状态。 |

### 5.3 需要调整的优先级

原计划里 P8 是“内存与代码变体探索”。现在建议改成：

```text
P8a：AI shadow/offline replay
P8b：AI order-only non-final A/B
P8c：必要时 memory/code variants
```

原因：

```text
1. memory/code variants 可能涉及更大工程风险。
2. AI order-only sidecar 如果做得好，风险比 scheduler rewrite 小。
3. AI offline replay 不影响语义，且能利用前面所有 telemetry。
```

但这不意味着 AI 早于 deterministic 调优成为主线。AI 在 P8 之前只能读数据和做 replay。

---

## 6. AI 加速的安全合同

### 6.1 AI 允许做什么

AI 第一阶段只允许做：

```text
1. 候选排序建议：order_only
2. UNKNOWN/UNPROVEN triage 分类
3. 调优实验解释与 profile 推荐
4. CP-SAT partial hint 建议
5. runtime bottleneck report 总结
6. local repair window 建议
7. 非最终实验脚本生成/参数矩阵生成
```

### 6.2 AI 禁止做什么

AI 永远不能在未另行立项和证明的情况下做：

```text
1. 删除候选
2. 宣称候选不可行
3. 生成正式 cut
4. 修改 certified proof source
5. 修改 campaign hash truth source
6. 写入 data/checkpoints/
7. 写入 data/solutions/
8. 写入 data/blueprints/optimal_blueprint.json
9. 改 final preflight ready 语义
10. 发射 live non-dry-run final 168h command
11. 把 runtime report 标记为 certified/proof
12. 把 exploratory 结果混入 certified_exact 主线
```

### 6.3 AI artifact 命名空间

所有 AI 产物写入：

```text
.artifacts/phase3b_ai_accel_20260429/
.codex_test_logs/phase3b/ai_accel_20260429/
```

推荐结构：

```text
.artifacts/phase3b_ai_accel_20260429/
  00_contract/
  01_feature_dataset/
  02_offline_replay/
  03_unknown_triage/
  04_order_only_shadow/
  05_order_only_ab_nonfinal/
  06_cp_sat_hints/
  07_runtime_diagnostics/
  08_model_registry/
  09_final_ai_recommendation/
```

不得写入：

```text
data/checkpoints/
data/solutions/
data/blueprints/optimal_blueprint.json
release/
viewer/
frontdoor/
.artifacts/*proof_source*
```

---

## 7. 完整阶段计划表

### 7.1 主计划总表

| 阶段 | 名称 | Lane | 目标 | 主要动作 | 产物 | 进入下一阶段条件 |
|---|---|---|---|---|---|---|
| S0 | Repair5 clean baseline | A | 确认最新包起点安全 | clean extract、py_compile、focused pytest、strict preflight no-write、dry-run、adversarial marker probe | `00_repair5_baseline_summary.md/json` | 159 tests 或最新 focused tests 通过；execution_allowed=false |
| S1 | Workspace + env freeze | A | 隔离实验空间 | 建 worktree/副本；确认 Python 3.13；必要时用 offline py313 bundle 装依赖；固定 BIOS/电源/后台负载 | `hardware_profile.json`、`workspace_manifest.json` | 环境记录完整，canonical path 只读 |
| S2 | Telemetry scaffold | A | 建观测底座 | process tree sampler、RSS/commit、CPU normalized、campaign telemetry reader、path mutation audit | `telemetry_samples.jsonl`、`run_summary.json` | baseline run 可完整采样 |
| S3 | Baseline reproduction | A+B | 重跑默认 profile | `prod_4x4_normal` 短测/中短测；重跑 1x1/2x4/2x8 对照 | `baseline_scorecard.md/json` | 建立可比较 baseline_score |
| S4 | AI dataset v0 shadow | C | 只读抽特征 | 从 S3 telemetry 抽 candidate/run/profile 特征；不训练或只生成统计 | `candidate_runs.jsonl`、`feature_schema.json` | schema 稳定；不写 canonical path |
| S5 | Config-only short matrix | B | 扫进程×worker | 300s/600s 随机顺序矩阵；插入 B0 baseline；记录热/内存/推进 | `matrix_short_scoreboard.md/json` | top 20% profile；或无收益结论 |
| S6 | Stage-specific workers | B | 利用当前 stage env | master/local/binding/routing 分开配置；优先 4x 与 3x | `stage_worker_scoreboard.md/json` | 至少 1-3 个 profile 进入中测，或维持默认 |
| S7 | Priority/Affinity exploratory | B | 测 P/E 调度与 priority | 先识别 CPU topology；只对 top profiles 跑 high/affinity/reserve-E | `affinity_priority_report.md/json` | mapping 可信且收益可复现，否则降级为探索 |
| S8 | Medium confirmation | B | 确认 deterministic top profiles | 1h-3h 非最终 repeat；baseline interleave；热态控制 | `medium_confirmation_report.md/json` | 候选相对 baseline >=15%，CV<=10%，内存/热安全 |
| S9 | AI offline replay | C | 判断 AI 是否值得接入 | 用 S3-S8 数据训练/回放 ranker；只比较排序收益，不影响 run | `offline_replay_report.md/json` | replay 显示 order-only 有稳定收益；无 data leakage |
| S10 | AI order-only shadow | C | 生成排序建议但不使用 | 产出 suggestion 文件；scheduler 忽略或只 dry-run 比较 | `candidate_rank_suggestions.json`、`shadow_diff.md` | candidate set hash 不变；重复生成一致 |
| S11 | AI order-only non-final A/B | C+B | 小规模 A/B 验证 | 同 profile 下 default order vs AI order；非最终 workspace；AI 只改顺序 | `ai_order_ab_report.md/json` | 有效推进率提升，UNKNOWN 不恶化，安全 path 无写入 |
| S12 | CP-SAT hint experiments | C | 尝试 hint 加速 | nearest-neighbor hint / 小模型 hint；只作为 solver hint，不作约束 | `hint_experiment_report.md/json` | status 不变、模型约束不变、runtime 有收益 |
| S13 | Runtime diagnostics sidecar | D | 用 IndustrialPlanner report 辅助诊断 | 只读蓝图/runtime report；bottleneck timeline；local repair window 建议 | `.artifacts/blueprint-runtime/*`、`runtime_ai_diag.md` | 不接 exact proof，不写 checkpoint |
| S14 | Memory/code variants | B/C | 只有必要时做代码优化 | telemetry-only、runner-only 优先；lazy-load/mmap 需单独风险评估 | `code_variant_report.md/json` | tests 通过，proof semantics 不变，收益可解释 |
| S15 | Candidate freeze | A+B+C | 冻结最终候选 | 可能是 `profile-only`，也可能是 `profile + AI order-only`；默认仍不改 production | `final_candidate_manifest.json` | 完整 scorecard 与 rollback plan |
| S16 | Fresh production acceptance | A+B | 刷新验收 | 同 artifact set，fresh benchmark，validator/gate 可重建 | `fresh_acceptance_summary.json` | campaign_valid_after_run=true，无 duplicated work |
| S17 | Gate revalidation | A | 确认安全语义未破坏 | focused tests、negative probes、strict preflight no-write、dry-run | `gate_revalidation_summary.json` | ready 只表示请求人工授权；execution_allowed=false |
| S18 | Final recommendation | A+B+C+D | 输出最终建议 | 保持默认 / 请求 profile change review / 请求更长非最终确认 | `final_acceleration_tuning_report.md/json` | 不授权 final 168h |

### 7.2 关键依赖关系

| 后续阶段 | 必须依赖 |
|---|---|
| AI dataset v0 | S2 telemetry scaffold + S3 baseline reproduction |
| AI offline replay | 至少 S3-S6 的多 profile 数据 |
| AI order-only A/B | replay gate 通过 + AI contract tests 通过 |
| CP-SAT hints | candidate-level variable/hint extraction 可稳定复现 |
| Affinity profile | P/E logical ID mapping 可信 |
| Memory/code variants | config/stage/AI order-only 都收益不足，或证据显示内存是瓶颈 |
| Fresh production acceptance | final candidate 已冻结，且不是 exploratory-only |
| Final recommendation | fresh acceptance + gate revalidation 全通过 |

---

## 8. 每阶段详细执行表

### S0：Repair5 clean baseline

| 项 | 内容 |
|---|---|
| 目标 | 从最新 Repair5 包确认起点安全。 |
| 输入 | `phase3b_pre_production_full_audit_upload_20260429_repair5_20260429_213207.zip` |
| 命令 | 使用包内 7zz clean extraction；运行 py_compile、focused pytest、preflight no-write、dry-run、adversarial probe。 |
| 输出 | `.artifacts/phase3b_accel_tuning/00_baseline/repair5_clean_baseline_summary.md/json` |
| 通过条件 | focused tests 通过；final preflight ready 只表示 request human authorization；`execution_allowed=false`；`final_168h_authorized=false`。 |
| 失败处理 | 停止调优；先修 package/gate/security 问题。 |

建议命令：

```powershell
python -m pytest -q `
  src/tests/test_phase3b_b5a_certified_anchor_promotion_review_packet.py `
  src/tests/test_phase3b_b5a_gate_integration_marker.py `
  src/tests/test_phase3b_long_run_preflight.py `
  src/tests/test_phase3b_prod_4x4_normal_dry_run.py

python scripts/build_phase3b_long_run_preflight.py `
  --production-acceptance-summary .codex_test_logs/phase3b/production_acceptance_after_change.json `
  --production-acceptance-result-validator .artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator_after_refresh_20260427/anchor119_row_domain_acceptance_result_validator.json `
  --b5a-gate-integration-marker .artifacts/phase3b_b5a_gate_integration_marker_20260426/b5a_gate_integration_marker.json `
  --no-write

python scripts/build_phase3b_prod_4x4_normal_dry_run.py --no-write
```

---

### S1：Workspace 与环境冻结

| 项 | 内容 |
|---|---|
| 目标 | 确保所有调优/AI 产物在独立实验空间，避免污染 Repair5 audit package。 |
| 输入 | clean extracted repo |
| 动作 | 建 `exp/phase3b-accel-tuning-ai` branch/worktree；确认 Python 3.13；记录 OS/BIOS/power plan/ambient。 |
| 输出 | `workspace_manifest.json`、`hardware_profile.json` |
| 通过条件 | canonical repo paths 不被实验写入；Python 3.13 可用；依赖可复现。 |

推荐目录：

```text
D:\phase3b_accel_tuning\repair5_baseline_clean\       # 只读基线
D:\phase3b_accel_tuning\repair5_exp\                  # 修改与实验
D:\phase3b_accel_tuning\repair5_runs\                 # workspace outputs
```

Linux/Codex sandbox 可对应为：

```text
/mnt/data/phase3b_accel_tuning/repair5_baseline_clean/
/mnt/data/phase3b_accel_tuning/repair5_exp/
/mnt/data/phase3b_accel_tuning/repair5_runs/
```

如果需要动态审查依赖，优先使用上传的 `offline_linux_py313_full_devtest_bundle_resolved.zip`，不要误用 Python 3.11 环境做最终口径。

---

### S2：Telemetry scaffold

| 项 | 内容 |
|---|---|
| 目标 | 同时服务 deterministic 调优和 AI 数据集。 |
| 输入 | baseline repo、campaign telemetry、process tree |
| 新增模块 | `src/runtime/hardware_profile.py`、`src/runtime/process_tree_telemetry.py`、`scripts/run_phase3b_local_tuning_profile.py`、`scripts/summarize_phase3b_local_tuning_matrix.py` |
| 输出 | `telemetry_samples.jsonl`、`run_summary.json`、`run_summary.md` |
| 通过条件 | 能采样 CPU/RSS/thread/IO/campaign progress；能 audit canonical path mutation。 |

必采指标：

| 类别 | 指标 |
|---|---|
| CPU | raw process tree CPU%、normalized machine CPU%、per-process CPU time、thread count |
| Memory | RSS、Private Bytes/USS、commit、peak commit、pagefile growth |
| Solver | solve attempts、candidate results、terminal results、UNKNOWN density、deterministic time、branches、conflicts |
| Campaign | candidate key、selection reason、frontier metrics、precheck eliminations、status counts |
| Safety | canonical path mtime/hash diff、checkpoint/solution/proof-source write detection |
| Optional | P/E core utilization、thermal throttling、package temp/power |

输出样例：

```json
{
  "schema": "phase3b_local_telemetry_sample_v1",
  "run_id": "s3_b0_prod_4x4_normal_r1",
  "t_wall": 123.4,
  "root_pid": 12345,
  "child_pids": [12346, 12347, 12348, 12349],
  "raw_process_tree_cpu_percent": 1375.0,
  "normalized_machine_cpu_percent": 57.3,
  "rss_bytes_total": 30661275648,
  "commit_bytes_estimated": 34100000000,
  "thread_count_total": 96,
  "hard_faults_per_sec": null,
  "package_temp_c": null,
  "thermal_throttling": null,
  "canonical_path_mutation_detected": false
}
```

---

### S3：Baseline reproduction

| 项 | 内容 |
|---|---|
| 目标 | 用增强 telemetry 重跑当前默认与对照 profile。 |
| 输入 | 当前 `prod_4x4_normal`、acceptance artifacts |
| profile | `prod_1x1`、`prod_2x4`、`prod_4x4_normal`、`prod_2x8`、可选 `prod_4x4_high` |
| 输出 | `baseline_scorecard.md/json` |
| 通过条件 | 得到有效推进率、内存、CPU、UNKNOWN、precheck 的 baseline。 |

评分不只看 candidate/sec。至少记录：

```text
useful_terminal_results_per_hour
solve_attempts_per_hour
candidate_results_per_hour
precheck_eliminations_per_hour
unknown_density
master_deterministic_time_per_wall_second
peak_rss_gib
peak_commit_gib
normalized_cpu_percent_avg/p95
thermal_throttling_detected
safety_path_mutation_detected
```

---

### S4：AI dataset v0 shadow

| 项 | 内容 |
|---|---|
| 目标 | 先抽数据，不训练、不影响运行。 |
| 输入 | S3 baseline telemetry、campaign state、campaign telemetry |
| 新增模块 | `src/ai_accel/feature_extract.py`、`src/ai_accel/schemas.py` |
| 输出 | `.artifacts/phase3b_ai_accel_20260429/01_feature_dataset/candidate_runs.jsonl` |
| 通过条件 | 同一输入重复抽取结果一致；无 canonical write。 |

候选样本字段建议：

```json
{
  "schema": "phase3b_ai_candidate_run_sample_v0",
  "candidate_key": "67x13:...",
  "run_id": "s3_b0_prod_4x4_normal_r1",
  "profile_id": "prod_4x4_normal",
  "parallel_processes": 4,
  "worker_profile": {
    "master": 4,
    "local_capacity": 4,
    "binding": 4,
    "routing": 4
  },
  "selection_reason": "probe_head",
  "frontier_candidate_metrics": {},
  "precheck": {
    "triggered": true,
    "eliminated": false,
    "reason": null
  },
  "terminal": {
    "status": "UNKNOWN",
    "outcome": "unknown",
    "classification": "master_unknown",
    "subtype": "master_start_incompatible_unknown"
  },
  "solver_metrics": {
    "wall_time": 0.0,
    "deterministic_time": 0.0,
    "branches": 0,
    "conflicts": 0,
    "hinted_literals": 0
  },
  "resource_metrics": {
    "rss_gib_at_window": 0.0,
    "normalized_cpu_percent_avg": 0.0
  },
  "labels": {
    "became_terminal_fast": false,
    "precheck_eliminated": false,
    "high_prune_gain": false,
    "unknown_risk": true
  }
}
```

---

### S5：Config-only short matrix

| 项 | 内容 |
|---|---|
| 目标 | 不改代码语义，只扫 `parallel_processes × global workers`。 |
| 输入 | S2 telemetry runner |
| 输出 | `matrix_short_scoreboard.md/json` |
| 通过条件 | 找到 top profiles，或明确无收益。 |

第一批矩阵优先级：

| profile | process_count | global workers | 备注 |
|---|---:|---:|---|
| B0 `4x4` | 4 | 4 | baseline |
| `3x6` | 3 | 6 | 18 worker 上限，较少进程复制 |
| `3x8` | 3 | 8 | 24 worker 上限，内存中等 |
| `4x5` | 4 | 5 | 20 worker 上限，保持当前进程数 |
| `4x6` | 4 | 6 | 24 worker 上限，RSS/热风险更高 |
| `2x10` | 2 | 10 | 20 worker 上限，低 RSS 深并行 |
| `2x12` | 2 | 12 | 24 worker 上限，低进程高 worker |
| `1x16` | 1 | 16 | 单进程深搜索对照 |
| `1x24` | 1 | 24 | 只短测，不长测 |
| `5x3` | 5 | 3 | 15 worker，测试更多进程 |
| `5x4` | 5 | 4 | 20 worker，RSS 警戒 |

停止条件：

```text
peak RSS > 42 GiB
commit charge > 44 GiB
pagefile 持续增长
thermal throttling 持续发生
canonical path mutation detected
系统/Codex UI 长时间不可用
```

---

### S6：Stage-specific worker matrix

| 项 | 内容 |
|---|---|
| 目标 | 利用当前已支持的 stage-specific env，低风险精调 worker 分配。 |
| 输入 | S5 top profiles |
| 输出 | `stage_worker_scoreboard.md/json` |
| 通过条件 | 找到更高有效推进率组合，或确认 global=4 已足够。 |

推荐矩阵：

| ID | process_count | master | local_capacity | binding | routing | 目的 |
|---|---:|---:|---:|---:|---:|---|
| W0 | 4 | 4 | 4 | 4 | 4 | 当前默认 |
| W1 | 4 | 6 | 4 | 2 | 4 | 提高 master，降低 binding |
| W2 | 4 | 8 | 4 | 2 | 4 | master 接近 built-in default |
| W3 | 4 | 6 | 6 | 2 | 6 | 平衡型 |
| W4 | 4 | 8 | 6 | 2 | 6 | master 偏高型 |
| W5 | 3 | 8 | 8 | 2 | 8 | 3进程高 per-process |
| W6 | 3 | 8 | 6 | 2 | 6 | 3进程保守高 master |
| W7 | 2 | 12 | 8 | 2 | 8 | 2进程深搜索 |
| W8 | 2 | 16 | 8 | 2 | 8 | 单阶段高 master 探索 |

命令模板：

```powershell
$env:EXACT_MASTER_CP_SAT_WORKERS="8"
$env:EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS="6"
$env:EXACT_BINDING_CP_SAT_WORKERS="2"
$env:EXACT_ROUTING_CP_SAT_WORKERS="6"

python scripts/run_phase3b_local_tuning_profile.py `
  --parallel-processes 4 `
  --campaign-hours 0.25 `
  --workspace-root .codex_test_logs/phase3b/local_accel_tuning/workspaces/w4 `
  --telemetry-out .artifacts/phase3b_local_accel_tuning/w4.telemetry.jsonl
```

---

### S7：Priority / affinity exploratory

| 项 | 内容 |
|---|---|
| 目标 | 只在 top deterministic profiles 上探索 Windows/P-E 核调度。 |
| 前置 | CPU logical ID → P/E mapping 可信。 |
| 输出 | `affinity_priority_report.md/json` |
| 通过条件 | 性能收益可复现，系统响应不恶化。 |

不建议全矩阵铺开 high priority。只对 S5/S6 top 2-3 profile 做：

```text
normal / high
unpinned / reserve 2E / disjoint process groups
```

如果 P/E mapping 不可信，affinity 结果只能作为 exploratory note，不能进入最终 profile 依据。

---

### S8：Medium confirmation

| 项 | 内容 |
|---|---|
| 目标 | 确认 deterministic profile 的真实稳定收益。 |
| 输入 | S5-S7 top candidates |
| 输出 | `medium_confirmation_report.md/json` |
| 通过条件 | 至少两次 repeat，均相对 baseline >=15%，CV<=10%，内存/热安全。 |

保留候选数量：

```text
baseline B0
best config-only 2 个
best stage-specific 2 个
best affinity/priority 1 个
```

总数最好不超过 6-7 个。

---

### S9：AI offline replay

| 项 | 内容 |
|---|---|
| 目标 | 在不影响 run 的前提下，验证 AI 候选排序是否有实际价值。 |
| 输入 | S3-S8 candidate_runs.jsonl、telemetry、scoreboards |
| 新增模块 | `src/ai_accel/train_candidate_ranker.py`、`src/ai_accel/replay_scheduler.py`、`src/ai_accel/triage_unknowns.py` |
| 输出 | `offline_replay_report.md/json` |
| 通过条件 | replay 在多个 profile 上稳定提前获得 useful terminal/prune/precheck-heavy results。 |

第一版模型建议：

```text
不要上深度学习。
先用 LogisticRegression / RandomForest / LightGBM / XGBoost / rank heuristic。
如果本地依赖不足，先用 sklearn 或纯规则 ranker。
```

离线 replay 指标：

```text
time_to_first_terminal_improvement
useful_terminal_results_at_fixed_budget
precheck_eliminations_at_fixed_budget
unknown_density_at_fixed_budget
profile_robustness
rank_stability_across_repeats
```

防止数据泄漏：

```text
1. 按 run_id / time split，不要同一个 candidate 的未来结果泄漏到过去 replay。
2. 训练标签不能使用当前 run 中尚未发生的 terminal 结果作为实时特征。
3. 所有 candidate 必须仍在 candidate universe 里；不能因模型低分被删除。
```

---

### S10：AI order-only shadow

| 项 | 内容 |
|---|---|
| 目标 | 生成排序建议文件，但 scheduler 只 dry-run 或忽略。 |
| 输入 | S9 ranker/replay 通过结果 |
| 输出 | `candidate_rank_suggestions.json`、`shadow_order_diff.md` |
| 通过条件 | candidate set 完全相同；重复生成顺序一致；schema 校验通过。 |

建议 schema：

```json
{
  "schema": "phase3b-ai-accel-suggestion/v0",
  "mode": "order_only",
  "source": {
    "campaign_state": "read_only",
    "telemetry": "read_only",
    "model": "candidate_ranker_baseline_v0"
  },
  "safety": {
    "may_drop_candidates": false,
    "may_create_cuts": false,
    "may_write_checkpoints": false,
    "may_modify_proof_source": false,
    "may_promote_certified_status": false
  },
  "candidate_universe_hash": "sha256:...",
  "suggestions": [
    {
      "candidate_id": "...",
      "rank": 1,
      "score": 0.873,
      "reason_codes": [
        "high_predicted_prune_gain",
        "low_unknown_risk",
        "similar_terminal_history"
      ]
    }
  ]
}
```

新增测试：

```text
src/tests/test_phase3b_ai_accel_contracts.py
```

至少断言：

```text
AI suggestion 不能删除候选
AI suggestion 不能新增候选
AI suggestion 不能写 data/checkpoints
AI suggestion 不能写 data/solutions
AI suggestion schema 中 may_drop_candidates=false
AI suggestion 缺失/损坏时 scheduler 回退 deterministic order
```

---

### S11：AI order-only non-final A/B

| 项 | 内容 |
|---|---|
| 目标 | 小规模非最终 run 中验证 AI order-only 的实际收益。 |
| 输入 | S10 suggestion file、S8 deterministic best profile |
| 输出 | `ai_order_ab_report.md/json` |
| 通过条件 | 有效推进率提升，UNKNOWN 不恶化，安全 path 无写入。 |

A/B 设计：

| Arm | profile | order | AI 权限 |
|---|---|---|---|
| A | deterministic best | default deterministic order | 无 |
| B | deterministic best | AI order-only suggestions | 只改变顺序 |
| C | baseline 4x4 | default deterministic order | 无 |
| D | baseline 4x4 | AI order-only suggestions | 只改变顺序 |

A/B 不能使用最终 168h；建议先 300s/600s，再 1h 非最终确认。

通过阈值建议：

```text
短测：相对同 profile default order 有效推进率 >=10%
中测：相对同 profile default order 有效推进率 >=15%
UNKNOWN density 不上升超过 5%
precheck/terminal useful 不下降
candidate universe hash 完全相同
```

---

### S12：CP-SAT hint experiments

| 项 | 内容 |
|---|---|
| 目标 | 让 AI/历史近邻只提供 solver hint，不改约束。 |
| 输入 | 已解决/已尝试 candidates 的变量赋值、warm-start metadata |
| 输出 | `hint_experiment_report.md/json` |
| 通过条件 | 终态语义不变；hint 不作为 constraint；runtime/branches/conflicts 有收益。 |

第一版不要直接训练深度模型。建议顺序：

```text
1. nearest-neighbor historical hint
2. rule-based hint portfolio
3. lightweight classifier/ranker 选择 hint source
4. 若样本足够，再考虑 GNN/NN hint predictor
```

hint 允许影响：

```text
AddHint / partial assignment
变量值尝试顺序
hint source 选择
```

hint 禁止影响：

```text
constraint set
objective correctness
candidate feasibility declaration
proof/cut/certification status
```

---

### S13：Runtime diagnostics sidecar

| 项 | 内容 |
|---|---|
| 目标 | 用 IndustrialPlanner runtime report 诊断蓝图瓶颈，但不接入 exact proof。 |
| 输入 | blueprint runtime execution plan、IndustrialPlanner headless harness、exact 输出蓝图或 public blueprint |
| 输出 | `.artifacts/blueprint-runtime/*.report.json`、`.artifacts/phase3b_ai_accel_20260429/07_runtime_diagnostics/*.md` |
| 通过条件 | 只读 exact 输出；不写 checkpoint；runtime report 不标记为 proof。 |

该 lane 与 exact 调优的关系：

```text
短期：不影响 exact campaign，只做 runtime bottleneck 解释。
中期：可帮助人工理解最终蓝图或 candidate 结构。
长期：可为 local repair / Neural LNS 提供探索数据，但仍不能形成 certified proof。
```

---

### S14：Memory/code variants

| 项 | 内容 |
|---|---|
| 目标 | 只有当配置/AI order-only 不够时，再做代码层优化。 |
| 优先级 | telemetry-only > runner-only > benchmark tooling > memory attribution > lazy-load > mmap/shared memory > scheduler rewrite |
| 输出 | `code_variant_report.md/json` |
| 通过条件 | tests 通过；proof semantics 不变；收益可解释。 |

允许优先做：

```text
1. telemetry-only improvements
2. local tuning runner 参数化
3. benchmark_parallelism matrix 扩展
4. memory attribution report
5. AI suggestion loader 的 dry-run/order-only path
```

暂不建议第一轮做：

```text
1. exact_parallel_scheduler 大改
2. shared process pool redesign
3. candidate selection 语义修改
4. proof-producing solver 语义修改
5. runtime elimination
6. 任何会改 artifact hash truth source 的优化
```

---

### S15：Candidate freeze

| 项 | 内容 |
|---|---|
| 目标 | 冻结最终候选，准备 fresh acceptance。 |
| 可能候选 | `profile-only` / `profile + stage workers` / `profile + AI order-only sidecar` / `keep current default` |
| 输出 | `final_candidate_manifest.json`、`rollback_plan.md` |
| 通过条件 | 候选命名、边界、收益、风险、回滚都明确。 |

候选命名示例：

```text
experimental_13900ks_htoff_3x8_stage_8_6_2_6_normal
experimental_13900ks_htoff_4x5_global_normal
experimental_13900ks_htoff_4x4_stage_8_6_2_6_ai_order_only_v0
```

即使 AI 表现好，也不要直接改：

```text
DEFAULT_PRODUCTION_PROFILE_ID
scripts/run_prod_4x4_normal.ps1
final preflight launch semantics
```

除非经过单独人工 profile-change review。

---

### S16：Fresh production acceptance refresh

| 项 | 内容 |
|---|---|
| 目标 | 用最新候选刷新 production acceptance。 |
| 输入 | frozen candidate profile、same artifact set |
| 输出 | `fresh_acceptance_summary.json`、`fresh_acceptance_result_validator.json` |
| 通过条件 | campaign_valid_after_run=true；duplicated_work=false；validator/gate 可重建。 |

如果候选包含 AI order-only：

```text
1. acceptance summary 必须显式记录 AI mode = order_only。
2. 必须记录 candidate_universe_hash 与 default run 一致。
3. 必须记录 may_drop_candidates=false。
4. 必须额外提供 AI suggestion schema hash。
5. 必须有 AI-off 对照 acceptance 或中测证据。
```

---

### S17：Gate revalidation

| 项 | 内容 |
|---|---|
| 目标 | 确认 Repair5 安全语义未破坏。 |
| 输入 | fresh acceptance、validator、B5A marker |
| 输出 | `gate_revalidation_summary.json` |
| 通过条件 | ready 只表示 request human launch authorization；execution_allowed=false；non-dry-run command not emitted。 |

必测 negative cases：

```text
minimal fake production acceptance summary -> rejected
shape-compatible fake validator -> rejected
wrong/missing validator chain hash -> rejected
duplicate/missing prod_4x4 or candidate record -> rejected
wrong selected_candidate -> rejected
wrong safe_area_upper_bound -> rejected
wrong frontier_candidates -> rejected
B5A marker exists=false/missing -> rejected
missing explicit production acceptance summary -> ready=false
missing explicit production acceptance result validator -> ready=false
missing explicit B5A marker -> ready=false
ready=true still emits no live non-dry-run command
AI suggestion tamper -> rejected or ignored
AI suggestion may_drop_candidates=true -> rejected
AI suggestion candidate universe hash mismatch -> rejected
```

---

### S18：Final recommendation

| 项 | 内容 |
|---|---|
| 目标 | 输出最终建议，不授权 final 168h。 |
| 输出 | `final_acceleration_tuning_report.md/json`、`scoreboard.csv/json`、`profile_change_patch_summary.md`、`rollback_plan.md` |
| 结论类型 | 保持默认 / 请求人工 profile-change review / 请求更长非最终确认 / 终止 AI 模块 |

machine-readable record：

```json
{
  "record_type": "phase3b_acceleration_tuning_ai_recommendation_v1",
  "package_reference": "phase3b_pre_production_full_audit_upload_20260429_repair5_20260429_213207.zip",
  "baseline_profile": "prod_4x4_normal",
  "recommended_profile": "prod_4x4_normal_or_experimental_candidate",
  "ai_accel_mode": "disabled|shadow_only|order_only_experimental|hint_experimental",
  "recommendation": "keep_current_default|request_human_profile_change_review|request_more_nonfinal_confirmation",
  "fresh_production_acceptance_passed": false,
  "gate_revalidation_passed": false,
  "execution_allowed": false,
  "final_168h_authorized": false,
  "runtime_elimination_authorized": false,
  "checkpoint_import_back_authorized": false,
  "release_viewer_frontdoor_promotion_authorized": false,
  "notes": []
}
```

---

## 9. AI 模块生命周期与扩展机制

AI 方向确实还没完全定，所以不能写成“固定模型 A 一定做到最后”。应该写成 registry + lifecycle。

### 9.1 AI module registry

新增：

```text
.artifacts/phase3b_ai_accel_20260429/08_model_registry/ai_module_registry.json
src/ai_accel/AI_ACCEL_REGISTRY.md
```

schema：

```json
{
  "schema": "phase3b_ai_accel_registry_v0",
  "modules": [
    {
      "module_id": "candidate_ranker_baseline_v0",
      "type": "order_only_ranker",
      "lifecycle_state": "shadow",
      "allowed_effects": ["candidate_order"],
      "forbidden_effects": [
        "drop_candidate",
        "create_cut",
        "write_checkpoint",
        "modify_proof_source",
        "promote_certified_status"
      ],
      "required_gates": [
        "schema_validation",
        "offline_replay",
        "order_only_contract_tests",
        "nonfinal_ab",
        "gate_revalidation"
      ],
      "promotion_status": "not_promoted"
    }
  ]
}
```

### 9.2 Lifecycle states

| 状态 | 含义 | 能做什么 | 不能做什么 |
|---|---|---|---|
| `idea` | 只是想法 | 写设计文档 | 运行实验证据不足 |
| `dataset_only` | 只抽数据 | feature extraction | 训练/推理影响 run |
| `offline_replay` | 离线回放 | replay、评分 | 改 scheduler |
| `shadow` | 生成建议但不使用 | 输出 suggestion | 影响实际顺序 |
| `nonfinal_ab` | 非最终 A/B | order-only A/B | final 168h |
| `accepted_experimental` | 实验接受 | 可被候选方案引用 | 默认生产启用 |
| `rejected` | 淘汰 | 保留报告 | 继续消耗主线资源 |
| `future_scope` | 后续再议 | 归档想法 | 当前执行 |

### 9.3 AI 模块晋升标准

AI 模块从 shadow 晋升到 nonfinal A/B 必须满足：

```text
1. schema 稳定
2. candidate universe hash 不变
3. offline replay 有稳定收益
4. 无 data leakage
5. contract tests 通过
6. 禁用 AI 后 deterministic fallback 完整
```

AI 模块从 nonfinal A/B 晋升到 accepted_experimental 必须满足：

```text
1. 至少两次 repeat 有收益
2. 相同 profile 下 AI-on > AI-off
3. UNKNOWN density 不明显恶化
4. 无 canonical path mutation
5. gate revalidation 通过
6. final_168h_authorized=false 仍成立
```

---

## 10. 评分方法

### 10.1 硬 gate

任意候选先过硬 gate：

```text
safety_path_mutation_detected = false
proof_semantics_changed = false
candidate_universe_changed = false，除非这是显式非 AI 的 exact-safe 改动且触发 campaign reset
fresh_tests_passed = true
peak_rss_gib <= 38 for normal candidate
peak_rss_gib <= 40 for guarded candidate
pagefile_growth_gib = 0 or negligible
thermal_throttling_detected = false
repeat_count >= 2 for candidate
final_168h_authorized = false
execution_allowed = false
```

### 10.2 综合评分

```text
score =
  40 * effective_progress_score
+ 15 * solver_quality_score
+ 15 * memory_headroom_score
+ 10 * repeatability_score
+  8 * safety_simplicity_score
+  7 * operational_simplicity_score
+  5 * AI_optional_value_score
```

解释：

| 分项 | 说明 |
|---|---|
| effective_progress_score | useful terminal/hour、candidate results/hour、precheck eliminations/hour，相对 baseline 归一。 |
| solver_quality_score | UNKNOWN density 降低、zero-branch UNKNOWN 减少、conflictful signal 有价值。 |
| memory_headroom_score | peak commit/RSS 距离 48GB 的余量。 |
| repeatability_score | repeat CV 越小越高。 |
| safety_simplicity_score | 越少碰 proof/gate/campaign hash 越高。 |
| operational_simplicity_score | config-only > stage workers > AI order-only > hints > memory code variants > scheduler rewrite。 |
| AI_optional_value_score | AI-on 相对 AI-off 的增益；若 AI 未启用则不扣核心分。 |

### 10.3 CPU 利用率解释规则

不能算成功的情况：

```text
CPU 从 60% 升到 95%，但 useful terminal/hour 没升。
CPU 满载导致 thermal throttling，长期吞吐下降。
CPU 满载但 UNKNOWN density 上升。
CPU 满载但 RSS/pagefile 进入危险区。
AI 排序让前期看起来更忙，但 terminal/prune/precheck useful 不增。
```

真正成功应表现为：

```text
有效推进率提高
内存安全
热稳定
可复现
candidate universe 不变
gate 不变宽松
```

---

## 11. 决策树

```text
开始
  ↓
S0 Repair5 baseline 不通过？
  → 停止：先修 package/gate/security，不做调优/AI。
  ↓
S2 telemetry 不足？
  → 先补 telemetry，不改 profile，不训练 AI。
  ↓
S5 config-only 无候选 > baseline 10%？
  → 进入 stage-specific；AI 仍只 shadow。
  ↓
S6 stage-specific 有候选？
  → 进入 medium confirmation。
  ↓
S8 deterministic candidate 稳定 > baseline 15%？
  → 冻结 profile-only 候选；AI 继续离线评估。
  ↓
S9 AI offline replay 无稳定收益？
  → AI 降级为 triage/report 工具，不进 scheduler。
  ↓
S11 AI order-only A/B 有稳定收益？
  → 可作为 experimental sidecar 候选。
  ↓
S12 hints 有收益但风险更高？
  → 保留为 future_scope 或 accepted_experimental，默认不进 final candidate。
  ↓
S16 fresh acceptance + S17 gate 全通过？
  → 输出 request_human_profile_change_review。
  ↓
任何时候 final 168h？
  → 本计划不授权；只能人工另行授权。
```

---

## 12. 最终合法结果

### 12.1 结果 A：保持默认 profile

适用条件：没有候选稳定超过 baseline，或收益不足以抵消风险。

交付：

```text
保留 telemetry tools
保留 AI dataset/replay reports
不改 DEFAULT_PRODUCTION_PROFILE_ID
不改 run_prod_4x4_normal.ps1
输出 keep_current_default
```

这是完全有效的最终结果。

### 12.2 结果 B：新增实验 profile，不改默认

适用条件：候选有希望，但证据不足以改默认。

交付：

```text
新增 experimental_13900ks_* profile
AI sidecar 仍是 shadow 或 nonfinal_ab
不改 DEFAULT_PRODUCTION_PROFILE_ID
输出 request_more_nonfinal_confirmation
```

### 12.3 结果 C：建议人工评审 default profile change

适用条件：profile-only 或 profile+AI order-only 在中测、fresh acceptance、gate revalidation 中均通过。

交付：

```text
提交 profile-change patch summary
提交 fresh acceptance artifacts
提交 gate revalidation artifacts
提交 rollback plan
输出 request_human_profile_change_review
final_168h_authorized=false
execution_allowed=false
```

### 12.4 结果 D：AI 模块终止或降级

适用条件：AI replay/A-B 无稳定收益、存在数据泄漏、或者安全合同难以证明。

交付：

```text
AI module lifecycle_state=rejected 或 future_scope
保留 triage/report 价值
不接 scheduler
不影响 deterministic tuning 结论
```

---

## 13. 推荐第一批任务清单

### Task A：把现有调优计划改成一体化计划

```text
文件：docs/phase3b_repair5_acceleration_tuning_ai_plan.md
动作：加入 AI safety contract、AI registry、AI shadow/offline/A-B 阶段。
验收：计划中明确 performance tuning 仍是 post-audit experimental branch。
```

### Task B：实现 telemetry + local tuning runner

```text
新增：
  src/runtime/hardware_profile.py
  src/runtime/process_tree_telemetry.py
  scripts/build_phase3b_local_hardware_profile.py
  scripts/run_phase3b_local_tuning_profile.py
  scripts/summarize_phase3b_local_tuning_matrix.py

验收：
  能跑 prod_4x4_normal 300s 非最终 run
  输出 telemetry_samples.jsonl + run_summary.json
  canonical path audit 通过
```

### Task C：重跑 baseline reproduction

```text
运行：
  prod_1x1
  prod_2x4
  prod_4x4_normal
  prod_2x8

输出：
  baseline_scorecard.md/json
```

### Task D：AI dataset v0

```text
新增：
  src/ai_accel/schemas.py
  src/ai_accel/feature_extract.py

输出：
  candidate_runs.jsonl
  feature_schema.json

验收：
  重复抽取一致
  不写 checkpoint/solutions/proof-source
```

### Task E：config-only + stage-specific matrix

```text
先跑：
  3x6, 3x8, 4x5, 4x6, 2x10, 2x12

再跑：
  4x stage 8/6/2/6
  3x stage 8/8/2/8
  2x stage 12/8/2/8

输出：
  matrix_short_scoreboard.md/json
  stage_worker_scoreboard.md/json
```

### Task F：AI offline replay

```text
新增：
  src/ai_accel/train_candidate_ranker.py
  src/ai_accel/replay_scheduler.py
  src/ai_accel/triage_unknowns.py

验收：
  replay 不能改变 candidate universe
  replay 不能使用未来泄漏特征
  输出 replay gains 与 failure cases
```

### Task G：AI order-only contract tests

```text
新增：
  src/tests/test_phase3b_ai_accel_contracts.py

断言：
  may_drop_candidates=false
  no checkpoint writes
  no proof-source writes
  malformed suggestion fallback deterministic
  candidate universe hash mismatch rejected
```

### Task H：非最终 A/B

```text
输入：
  deterministic best profile
  AI suggestion file

运行：
  default order vs AI order-only
  300s/600s -> 1h repeat

输出：
  ai_order_ab_report.md/json
```

### Task I：fresh acceptance + gate revalidation

```text
只有 final candidate freeze 后执行。
输出：
  fresh_acceptance_summary.json
  gate_revalidation_summary.json
  final_acceleration_tuning_report.md/json
```

---

## 14. 文件结构建议

```text
src/runtime/
  hardware_profile.py
  process_tree_telemetry.py
  windows_cpu_topology.py             # optional
  windows_perf_counters.py            # optional

src/ai_accel/
  __init__.py
  schemas.py
  feature_extract.py
  train_candidate_ranker.py
  replay_scheduler.py
  rank_candidates.py
  triage_unknowns.py
  hint_extract.py
  hint_emit.py
  contract.py

scripts/
  build_phase3b_local_hardware_profile.py
  run_phase3b_local_tuning_profile.py
  summarize_phase3b_local_tuning_matrix.py
  build_phase3b_ai_candidate_dataset.py
  build_phase3b_ai_rank_suggestions.py
  replay_phase3b_ai_scheduler.py

src/tests/
  test_phase3b_local_tuning_profiles.py
  test_phase3b_ai_accel_contracts.py
  test_phase3b_ai_accel_replay.py

.artifacts/
  phase3b_local_accel_tuning_20260429/
  phase3b_ai_accel_20260429/

.codex_test_logs/phase3b/
  local_accel_tuning_20260429/
  ai_accel_20260429/
```

---

## 15. 要写进测试的安全断言

| 测试 | 断言 |
|---|---|
| `test_ai_suggestion_schema_order_only` | `mode=order_only`，`may_drop_candidates=false`，`may_create_cuts=false`。 |
| `test_ai_suggestion_candidate_universe_hash` | hash mismatch 时拒绝或忽略 suggestion。 |
| `test_ai_suggestion_no_drop_no_add` | suggestion 覆盖不足也不能减少 candidate universe。 |
| `test_ai_missing_file_fallback` | suggestion file 缺失时 deterministic order 完全不变。 |
| `test_ai_malformed_file_fallback` | schema 错误时 deterministic order 完全不变。 |
| `test_ai_no_checkpoint_write` | AI 工具运行后 `data/checkpoints/` mtime/hash 不变。 |
| `test_ai_no_solution_write` | AI 工具运行后 `data/solutions/` mtime/hash 不变。 |
| `test_ai_no_preflight_mutation` | AI 模块不能让 preflight gate 变宽松。 |
| `test_experimental_profiles_not_default` | 所有 `experimental_13900ks_*` 默认 false。 |
| `test_final_168h_not_authorized` | 所有调优/AI runner 不能启动 final 168h。 |

---

## 16. 风险表

| 风险 | 触发方式 | 处理 |
|---|---|---|
| AI 被误当 proof | AI 输出 candidate infeasible/certified | AI schema 禁止；tests 拒绝；final report 明确 AI 只 order/hint。 |
| AI 偷偷 drop candidate | suggestion 只给 top K | scheduler 必须保留完整 candidate universe，未建议候选追加 deterministic tail。 |
| 调优污染 checkpoint | runner workspace 配错 | path audit；canonical mtime/hash diff；发现即 disqualify。 |
| CPU 满载但推进率没升 | worker 过多、热降频、UNKNOWN 变多 | 以 useful terminal/hour 和 UNKNOWN density 为主评分。 |
| 5/6 进程触发 pagefile | RSS/commit 过高 | 5x 只短测；6+ 默认禁止，除非实测 headroom。 |
| P/E affinity 不可信 | logical ID mapping 错 | mapping confidence 低时 affinity 只能 exploratory。 |
| AI 数据泄漏 | replay 用未来结果做特征 | time split / run split；feature whitelist；leakage test。 |
| hints 改变语义 | hint 变成约束 | 只用 solver hint API；模型 proto diff；约束 hash 比对。 |
| runtime sidecar 反向污染 exact | runtime report 被当 proof | 输出仅 `.artifacts/blueprint-runtime/`；不写 exact paths。 |
| profile change 过早 | 短测偶然高 | 必须 repeat + medium confirmation + fresh acceptance + gate revalidation。 |

---

## 17. 最终推荐执行节奏

### 第一周/第一轮：不要碰 AI scheduler

```text
S0-S4：clean baseline、workspace、telemetry、baseline reproduction、AI dataset v0。
```

目标是把“我们到底快在哪里、慢在哪里、内存在哪里爆、UNKNOWN 在哪里聚集”讲清楚。

### 第二轮：deterministic 调优为主

```text
S5-S8：config-only matrix、stage-specific workers、priority/affinity、medium confirmation。
```

优先找一个不靠 AI 的稳定 profile。这样即使 AI 失败，调优主线也不会崩。

### 第三轮：AI 从 replay 到 order-only

```text
S9-S11：AI offline replay、order-only shadow、non-final A/B。
```

AI 的第一个可落地方向只做排序，不做剪枝。

### 第四轮：hints/runtime/code variants 作为增强项

```text
S12-S14：CP-SAT hints、runtime diagnostics、必要的 memory/code variants。
```

这些都不能抢在 profile 与 telemetry 前面。

### 第五轮：冻结、验收、复验、建议

```text
S15-S18：candidate freeze、fresh acceptance、gate revalidation、final recommendation。
```

最终输出仍然只是请求人工评审或保持默认，不授权 final 168h。

---

## 18. 本计划的方向判断

当前最明朗、最可落地的路线是：

```text
deterministic profile tuning
  + stage-specific worker tuning
  + telemetry-driven AI candidate ranking sidecar
```

短期不要优先做：

```text
深度 GNN branch policy
端到端 RL 蓝图生成
shared-memory scheduler rewrite
runtime elimination
AI infeasibility classifier as proof
```

这些不是永远不能做，而是现在没有足够 telemetry、合同边界和 acceptance 证据支撑。

推荐最终集成形态：

```text
prod/exact runner
  ↓ reads optional
AI order-only suggestion file
  ↓ if valid
changes candidate order only
  ↓ exact solver still decides
campaign state / proof / gate unchanged
```

也就是：AI 让“先跑谁”更聪明，但“谁是真的可行/不可行/认证完成”仍然由 exact solver 和 gate 决定。

---

## 19. Definition of Done

本计划完成时，至少应满足：

```text
1. 最新 Repair5 baseline 已复验。
2. local telemetry scaffold 完成。
3. prod_4x4_normal baseline scorecard 完成。
4. config-only short matrix 完成。
5. stage-specific worker matrix 完成。
6. top deterministic profiles 经过 medium confirmation。
7. AI dataset v0 完成。
8. AI offline replay 完成。
9. AI order-only contract tests 完成。
10. 如果 AI 进入 A/B，则 AI-on 与 AI-off 对照完成。
11. 如果 CP-SAT hints 进入实验，则证明 hint 不改约束。
12. 如果 runtime diagnostics 启用，则输出只在 .artifacts/blueprint-runtime/。
13. final candidate manifest 完成。
14. fresh production acceptance 完成或明确未达到执行条件。
15. gate revalidation 完成。
16. final report 明确：execution_allowed=false，final_168h_authorized=false。
```

---

## 20. 最后建议

不要把“AI 加速还没定”理解成“没法做全流程计划”。

真正适合这个项目的计划不是锁死某个 AI 模型，而是锁死下面这些东西：

```text
边界：AI 不进 proof。
接口：AI 只通过 suggestion/hint/report sidecar 接入。
阶段：dataset -> replay -> shadow -> non-final A/B -> experimental。
验收：有效推进率、UNKNOWN density、内存、热、安全 gate。
退出：无收益或有风险就降级/终止，不拖累 deterministic 主线。
```

因此，这份一体化计划的主线非常明确：

```text
先让机器与 solver 被看清楚，
再把 13900KS 的 deterministic 性能榨出来，
再让 AI 在安全边界内做排序与诊断，
最后只把经过 fresh acceptance 和 gate revalidation 的候选提交给人工评审。
```
