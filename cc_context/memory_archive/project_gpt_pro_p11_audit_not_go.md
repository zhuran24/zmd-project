---
name: gpt-pro-p11-audit-not-go
description: 2026-05-22→23 GPT pro 11 round audit Phase 1.1 全 NOT GO → Step A-O 15 commit close. **2026-05-23 末**: 外部 exit hardening delivery 把 P1.2A 入门做完 + Gemini math review meta-audit 给 P1.2B 5 P0 acceptance. **Phase 1.1 GO**, 178 cuts pass.
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

## STATUS (2026-05-23 末): Phase 1.1 GO ✅, P1.2A 入门 ✅ done

外部 reviewer 给完整 Phase 1.1 exit hardening delivery (audit report + plan v2
+ 26 file patch). 8 项 fix 落地 (我们 plan §10 入门 7 项 + 1 新发现 test stub
unsafe 注入收紧). 178 cuts pass (172 → +6). mypy strict 全清 (37 → 0). radon
A 无 D. **Phase 1.1 GO blessed**, 可进 Phase 1.2.

同时另一份 Gemini math review meta-audit (Gemini 数学 review 的 meta-review)
给 5 P0 acceptance checklist for Phase 1.2 P1.2B:
- P0-A: F5 fallback bounded core minimizer (last verified, not unverified partial)
- P0-B: F9 area-only (拒 routing/binding overflow witness, PROJECT_LOCK 锁)
- P0-C: Step 8 apply-to-master 不能再悬空
- P0-D: F2/F4 generator 不能长期 stub (F4 容量 0 特例, F2 min-cut 主战场)
- P0-E: dark matter telemetry (unexplained infeasible jsonl)

3 个 critical 修正 (Gemini 大方向对但表述过满):
- F5 不能扛 132 集群 (是 fallback 不是主力, F5 ratio > 50% = stop-ship)
- F9 不能 routing/binding overflow → density (只 `area_capacity_overflow`)
- **CP-SAT 9.15 不支持 `AddLazyConstraint`** — 必须 LBBD 外循环 `solve → verify → generate → rebuild → solve`

Phase 1.3 加 P1.3A spike (CP-SAT attach 方式验证, 3 方向 PoC: solve-rebuild vs
C++ propagator hook vs hard-constraint rebuild). Spike GO 后才 P1.3B.

11 red fixture 补完 P1.2B 测试 (F5/F9/F2/F4/CP-SAT/DarkMatter).

### Step A-O 闭环 (15 commit src + 6 commit infra)

- **A** (3d35a62): validator schema assert → fail-closed (`python -O` 防线)
- **B** (45c44d2): F3 cert ↔ literal multiset 绑定
- **C** (eaed85c): F2 partition enclosure + cut_edges canonical
- **D** (5c06dff): F4 cert.src/sink_component == BFS 严等
- **E** (8a38401): F1 strict P(g)⊆R check (核心数学层)
- **F** (e0ec660): F1 evaluate 重算 cap_R + F4 separator_cells check
- **G** (3553efb): lru_cache(256) + F4 commodity_id spec align
- **H** (e5c41b9): Phase 1.3 perf opt TODO + Gemini r33-35 archive
- **I/J/K** (bdaa303): step_7 family dispatch + F3 slot binding + F4 separator
  in-grid + F2 evaluator enclosure
- **L** (a38620c): F1 contributing_groups 去重 + tuple demand + gap consistency
- **M** (273fbff): replay canonical_rules=None HOLD; F2/F4 commodity registry
  require
- **N** (afef8f1): F2 contributing 去重 + cross-partition; CutStore.add_cut
  default initial_state="held"
- **O** (c8fb7ef): F1 GHOST_AGNOSTIC ghost∩R=∅; F2/F4 reject GHOST_AGNOSTIC;
  on_ghost_rect_changed full replay gate; add_cut initial_state validate 前置

### Audit archive (累积 11 GPT round + 22 Gemini round + 1 plan doc)

- `external_review/gpt_pro_phase1_1_v{1,2,3,4,5,6}_audit_*.md` (11 archive)
- `cross_check/gemini_round_{14..35}*.md` (22 archive)
- `PHASE_POST_1_1_REFACTOR_PLAN.md` (1363 line / 54 KB, 18 section + 13 数学
  原理 subsection, commit d86d473)

### Review pkg v1-v8 演进

| 版本 | scope | size | trigger |
|---|---|---|---|
| v1 | cut framework only | 0.40 MB | Phase 1.1 大节点首次 |
| v2 | + README/COMMIT_LOG 删主动性内容 | 0.30 MB | 用户 feedback |
| v3 | + Step I/J/K 修 + GPT v2 archive | 0.30 MB | v2 NOT GO |
| v4 | + Step L 修 + GPT v3 archive | 0.31 MB | v3 NOT GO |
| v5 | + Step M 修 + GPT v4 archive | 0.32 MB | v4 NOT GO |
| v6 | + Step N 修 + GPT v5 archive | 0.33 MB | v5 NOT GO |
| v7 | + Step O 修 + GPT v6 archive (含 plan doc, 后删) | 0.34 MB | v6 NOT GO |
| **v8** | **全项目 scope + 7z 高压 + ship 7za binary** | **6.11 MB** | 用户要全 |

### v7 vs v8 重要 strategy 差

v7 仍 cut framework only (87 file). v8 全项目 (2728 file unzipped 102.8 MB)
+ 7z -mx=9 ultra (5.34 MB) + zip 壳 ([[review-pkg-7z-strategy]]) + ship
7za 解压工具 (Linux x64 1.59 MB).

### Phase 1.2 入门待 (task #241)

7 项 factual fix (per plan §10):
1. strict gate default ON (`EXACT_FAMILY_VALIDATOR_STRICT="0"→"1"`)
2. spec drift 7 处全清 (PoseId / family list / F3 direction / F1 region_kind
   / F2/F4 cert schema / source_digest)
3. source_digest 真 hash (替 "poc_source_digest")
4. ghost_rect tuple 语义 lock (object schema + 非方形 fixture)
5. mypy strict 37 errors → 0
6. radon validate_cutset D(27) / component_reach D(24) / port_exposure D(23) 拆 helper
7. evaluate_literal_port_exposure 删 vs 接入

---



## 2026-05-22 GPT pro Phase 1.1 audit verdict NOT GO

GPT pro 两次 (round 1 + round 2) 同 input pkg (`phase1_1_gpt_pro_review_v1.zip`
commit 868bef7) + 同 prompt, 不同 session, **两次 verdict 一致 NOT GO**.

archive:
- `docs/research/p3_b_design_v2_20260521/external_review/gpt_pro_phase1_1_audit_round1_NOT_GO.md`
- `docs/research/p3_b_design_v2_20260521/external_review/gpt_pro_phase1_1_audit_round2_NOT_GO.md`

## 2 P0 (两次 catch, 我都实测复现)

### P0-1: F1 demand_R 不满足 spec §2b 的 P(g) ⊆ R

src 推 contributing group 只看 `placement_rule_for_group`, 不验 group 真 pose
domain 是否全 ⊆ R. 真数据反例:

- `boundary_io` 46 instance, placement_rule="left_or_bottom_boundary"
- candidate_placements 54 boundary_storage_port pose:
  - wholly inside union: 40
  - wholly outside union: 14
  - mixed: 0
  - inside cells: 120, outside cells: 42
- 反例: `viewer::boundary_required_output_source_ore_005` 占
  (31,69)/(32,69)/(33,69) — 不在 union R

→ demand_R=46×3=138 不是 R 内严格下界. F1 cut 误剪合法状态.

### P0-2: F3 validator 不绑 cert ↔ literal

`port_exposure.py:63` 解构 `blocking_pose_id` 但 unused (vulture 也 catch).

反例: cert blocker `viewer::mfg_crusher_source_013`, cut.literals 错放
`viewer::mfg_crusher_source_014` (同 group 不同 pose) → validator `ok` +
evaluator `True`. 拿 p13 证剪 p14.

附 round 2 新发现: `python -O` 删 `assert len(cut.literals) >= 2` →
一元 literal 通过 schema_err 改 ok. **certified solver production 不能用
assert 守 schema**.

## 7 必修 (合并两次)

1. F1 demand_R 改用真 P(g) ⊆ R (GroupState.pose_domain + candidate_placements
   occupied_cells, 验所有 pose ⊆ R, 否则不算 contributing)
2. F1 加 14-outside-pose regression test
3. F3 validator 绑 cert.literals multiset 精确等于 cert
   {(facility_group, facility_pose_id), (blocking_group, blocking_pose_id)}
4. F3 (+ 所有 validator 入口) schema assert → 显式 `if ... return schema_err`
   (不依赖 assert, 生产 `python -O` 失效)
5. F2 + F4 validator 补强: F2 加 A∪B==free_cells + cut_edges 集合验 + commodity
   demand 重算; F4 加 commodity_id 真存在 + cert bitset==recomputed BFS +
   separator 真 blocked + commodity_route assumption verifier
6. Phase 1.2 前 F1-F9 strict registration gate
   (`EXACT_FAMILY_VALIDATOR_STRICT=1` 下未注册 fail-closed)
7. spec ↔ src ↔ data 三层 align:
   - state_machine_v2.md PoseId=int → str
   - cut_lifecycle_v2.md 9 family list 含 power_grid_reach / density_envelope,
     去 symmetry_lift
   - F2/F3/F4 cut_family_specs 跟 src 当前实施 align
   - source_digest 真实施 (替 placeholder "poc_source_digest")
   - mypy --strict 29 errors 清

## 静态质量

- ruff: 12 F401 tests unused (cosmetic)
- mypy --strict: 29 errors (commit 时只 --ignore-missing-imports)
- vulture: port_exposure.py:63 blocking_pose_id unused (跟 P0-2 同根)
- bandit: 14 low B101 assert_used (F3 schema assert 是真生产风险)
- radon: 平均 A 3.98; C 级热点 segment_aabb_intersection_t C(15) /
  validate_region_capacity C(13) / validate_port_exposure C(12) — F1/F3
  validator 在 soundness 边界上, 优先拆

## Verdict 反思

我之前 r30-r32 Gemini audit catch 15 个 gap, 但**漏 4 个 critical**. GPT
pro 这层是 **adversarial soundness audit** — 不是 happy-path 接合, 是问
"validator 能被假 cert 骗吗". Gemini prompt 偏 spec↔src/data 一致, 没 push
"构造反例 falsify cert 完整性".

下次实施 family validator 必须主动想: "假 cert 能不能 pass?" — 即 cert 本身
完整 (cert ↔ literals / cert ↔ region / cert ↔ commodity 一致性) 跟 cert
内字段 sound 性 是两层独立 audit.

## Refs

- [[external-review-reproducibility]]: GPT 两次 finding 通常不完全一致.
  本次 F1+F3 P0 两次重叠 — high confidence signal, 不是随机
- [[big-milestone-gpt-pro-review]]: 大节点打包 GPT pro
  审查规则
- [[gemini-prompt-audit-mode]]: Gemini audit mode 用真数据 + armor 比 GO 章
  好, 但仍漏 adversarial soundness 层
