---
id: pr2-5-b2-candidate-geometry-rederivation-landed
kind: decision
title: PR2 #5 B2 候选几何独立枚举——Option A(字节级重推 gate)2026-07-06 落地 commit 16495f4;含"三个 B2 同名不同物"消歧 + Option B(契约迁移)owner-only 残余
summary: 2026-07-06 落地 PR2 #5 B2 的 Option A。B2 是什么(先消歧,这点坑过我两次)：B2 = verifier 独立重推 candidate **几何**(candidate_placements.json 那 45MB 设施 pose 池)、不再把它当命名 TCB 死字节直接信。它 **≠** 两个同名物：①README §3 的"PR2-b B2"是 mint 接受 caller floor 的假-CERTIFIED 信道(早落 69980b3,无关)；②frontier **尺寸**域 candidate_generation(哪些幽灵矩形尺寸)——那个 anti-slice + 穷尽早已从冻结 canonical_rules 独立锚定(terminal_frontier_evidence_violation + _load_exact_* + test_pr2_5_child_elevation..._on_sliced_domain 切片拒绝测试),不是 B2。做了什么(Option A)：新 gate canonical_candidate_geometry_rederivation_violation(pr2_l0_artifact_core),child.verify 在 terminal precheck 后无条件调用——从冻结 canonical_rules 用 placement_generator.generate_all_pools 重推 pools、精确紧凑序列化 json.dumps(separators=(",",":"),allow_nan=False)、断言 sha256 == LOCKED_EXACT_ARTIFACT_SHA256["candidate_placements"](a914ba63…)，不等/异常 fail-closed。命根子实测：生成器从 canonical_rules ~1.5s 逐字节复现被钉 45MB(size 45774305/sha a914ba63)。配套：placement_generator 的 jsonschema import 惰性化(挪进 load_templates)让 stdlib-only child 能 import；L0 snapshot 白名单 24→25 加 src.placement.placement_generator；placement_generator 入 V99 floor 整文件钉死；checker 结构性封印 gate(进 child 期望 tail + _check_candidate_sink_replay_contract 必调 + import allowlist，谁删 gate checker 即红)。守卫 certified_project_uses_locked_artifact_contract 对真实仓库根(root==source_root)返 True → gate 生产必开火(非 no-op)。TCB 收缩含义(诚实、不 overclaim)：从"信 45MB 不透明字节"→"信可审计生成器源码(V99 floor)+ canonical_rules"；这是**同生成器重推证字节等值**、**非独立重实现**，生成器源码本身 + canonical→几何**语义**映射(非字节)仍是命名 TCB。Option B(把 candidate_placements 彻底移出证明权威 = 改 PROJECT_LOCK §1A/:196-203 证明契约)是 owner-only 残余、未做。验收：双 checker 绿、EOL 全 LF、--full 3822 passed(一次 flaky=预存并行 test_master 污染、隔离/整文件复现绿、非 B2)、--slow 30 passed、命根子重构后复核。文档注 25e530c(PROJECT_LOCK + soundness_gap_roadmap)。
scope:
  domains:
    - certified-exact
    - pr2
    - tcb
    - soundness
  paths:
    - src/search/pr2_l0_artifact_core.py
    - src/search/pr2_l0_true_verifier_child.py
    - src/placement/placement_generator.py
    - src/search/pr2_l0_micro_verifier_core.py
  symbols:
    - canonical_candidate_geometry_rederivation_violation
status: active
priority: P1
triggers:
  intents:
    - assess-whether-pr2-5-b2-done
    - understand-candidate-geometry-tcb
    - decide-option-b-contract-migration
    - disambiguate-which-b2
  keywords:
    - PR2 #5 B2
    - 候选域独立枚举
    - candidate_placements 重推
    - canonical_candidate_geometry_rederivation_violation
    - candidate geometry TCB
    - Option A
    - Option B 契约迁移
    - 三个 B2 撞车
    - candidate_generation 不是 B2
  negative_keywords: []
  paths:
    - src/search/pr2_l0_artifact_core.py
    - src/placement/placement_generator.py
  symbols:
    - canonical_candidate_geometry_rederivation_violation
  error_regex: []
  examples:
    - PR2 #5 B2 做完没 / 是什么
    - candidate_placements 还是不是命名 TCB
    - 该不该做 Option B 把 candidate_placements 移出证明权威
    - 哪个 B2(#5 候选几何 vs PR2-b mint-floor vs candidate_generation 尺寸域)
activation:
  layer_hint: L1
  must_know: false
  reason: 问"PR2 #5 B2 做完没/是什么"、碰 candidate_placements TCB、或规划 Option B 契约迁移时该读。记了 Option A 已落地(字节级重推 gate,commit 16495f4)、TCB 收缩的精确含义(同生成器证字节等值、非独立重实现)、Option B owner-only 残余、以及"三个 B2 同名不同物"消歧——后者坑过两次(误把 B2 当 candidate_generation)。
provenance:
  op: record
  reason: '2026-07-06 owner 令"再继续做到底",重开工程线做 #5 B2 并驱动到完成(实现+验收+提交+文档注)。存档:B2 真实内容(消歧)、Option A 落地事实与边界、Option B 残余,供未来重估与防同名混淆。'
  evidence:
    - "2026-07-06:实现+reseal commit 16495f4(10 文件),文档注 25e530c。codex 深查(a6f8430b)对 README:242/1107/1886 + PROJECT_LOCK:92-98/196-203 + soundness_gap_roadmap:20-21 坐实 B2=candidate_placements 几何、open。命根子:重生成脚本逐字节复现被钉 a914ba63。验收:双 checker/--full 3822/--slow 30 全绿。"
  updated_at: "2026-07-06"
---
2026-07-06 owner 令「再继续做到底」，重开工程线做 PR2 #5 B2 并驱动到完成。存事实 + 边界 + 消歧，供未来重估。

== 先消歧：三个「B2」同名不同物（我这次误判过两次，先钉死）==
- **PR2 #5 B2（本卡）= 候选几何独立枚举**：verifier 独立重推 `candidate_placements.json`（45MB 设施 pose 几何池）、不再当命名 TCB 死字节信。← 我做的这个。
- **PR2-b B2（README §3）= mint 接受 caller floor** 的假-CERTIFIED 信道，早落 `69980b3`。**无关**。
- **frontier 尺寸域 `candidate_generation`**（哪些幽灵矩形尺寸）：anti-slice + 穷尽早已从冻结 `canonical_rules` 独立锚定（`terminal_frontier_evidence_violation` + `_load_exact_*` + `test_pr2_5_child_elevation_..._on_sliced_domain`）。**不是 B2**。我本会话一度把 B2 误当成它、报「B2 已闭」，被 codex 完备性复核逮回。

== 做了什么（Option A，字节级重推 gate）==
- 新 gate `canonical_candidate_geometry_rederivation_violation`（`pr2_l0_artifact_core.py`）：从冻结 `canonical_rules` 用 `placement_generator.generate_all_pools` 重推 pools → `json.dumps(separators=(",",":"),allow_nan=False).encode("utf-8")` → `sha256` 断言 `== LOCKED_EXACT_ARTIFACT_SHA256["candidate_placements"]`；不等/异常 fail-closed。
- `child.verify`（`pr2_l0_true_verifier_child`）在 terminal precheck 后**无条件**调用、raise。
- 配套：`placement_generator` 的 `jsonschema` import 惰性化（挪进 `load_templates`）→ stdlib-only child 能 import 该模块；L0 snapshot 白名单 24→25 加 `src.placement.placement_generator`；该文件入 **V99 floor** 整文件钉死；checker **结构性封印** gate（进 child 期望 tail + `_check_candidate_sink_replay_contract` 必调 + import allowlist，谁删 gate → checker 红）。
- 守卫 `certified_project_uses_locked_artifact_contract` 对真实仓库根 `root==source_root` 返 True → **生产必开火、非 no-op**（正例测试用 `parents[2]` 源根走 True 分支真跑 sha 比对）。

== 边界（诚实，不 overclaim）==
- TCB 由「信 45MB 不透明字节」→「信可审计生成器源码（V99 floor）+ canonical_rules」。**同生成器重推证字节等值、非独立重实现**；生成器源码本身 + canonical→几何**语义**映射（非字节）仍命名 TCB。
- **Option B = 把 candidate_placements 彻底移出证明权威**（verifier 用自己重推的 pools、不再依赖被钉字节）= 改 `PROJECT_LOCK §1A`/`:196-203` 证明契约 = **owner-only 残余，未做**。

== 命根子 + 验收 ==
- 命根子实测：生成器从 canonical_rules **~1.5s 逐字节复现被钉 45MB**（size 45774305 / sha `a914ba63…c444b`），重构后复核仍成立。
- 双 checker 绿、EOL 全 LF、`--full` 3822 passed（一次 flaky = 预存并行 `test_master` 污染，隔离 0.57s / 整文件 227 复现绿，非 B2）、`--slow` 30 passed。commit `16495f4` + 文档注 `25e530c`。

关联：语义 TCB 硬地板 + 第四路 [[tcb-has-solver-hard-floor-replay-mandatory]]；主线排期(B2=批2b)[[p1-2-closeout-then-tcb-backlog-order]]；overclaim 教训根 [[extracting-proof-core-from-close-kernel-sink-sop]]；ship-then-sweep [[ship-then-sweep-docs-for-stale-narrative]]。
