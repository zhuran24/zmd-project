# 04 — 设计哲学 + 核心 invariants (含 PROJECT_LOCK §3A 边界)

cut framework 的数学基础 + 工程边界. 这些是 PROJECT_LOCK §3A 锁定的, 不是
review 时谁不爽改一改就行.

### 2.1 9 family 怎么定的 + 各 family 解决什么 INFEASIBLE 类

INFEASIBLE 不是单一现象. cut framework 拆成 9 类, 每类对应一个 cert schema +
validator + evaluator + oracle:

| Family | Mode | INFEASIBLE 类型 | spec |
|---|---|---|---|
| F1 region_capacity | geometric | 某 region R 内 cells per pose × demand > 可用 cap | spec §1-§9 |
| F2 cutset | geometric | partition (A, B) 上跨 partition demand > min-cut size (Menger) | 02_cutset.md |
| F3 port_exposure | literal | facility A 的 port 被 facility B 占, A+B 同选不可行 | 03_port_exposure.md |
| F4 component_reach | geometric | src/sink commodity 在 free_cells 图上 disconnected | 04_component_reach.md |
| F5 pattern_nogood | literal | 已知 INFEASIBLE 组合的最小化 (deletion / QuickXplain) | 05_pattern_nogood.md |
| F6 shape_packing_hall | geometric | Hall's marriage theorem 推 region 内 pose 数下界 | 06_shape_packing_hall.md |
| F7 power_hitting_set | literal | 电源 hitting set 不可满足 (sub-NP-hard) | 07_power_hitting_set.md |
| F8 power_grid_reach | geometric | Liang-Barsky AABB 推电网不可达 | 08_power_grid_reach.md |
| F9 density_envelope | geometric | region density 上界违反 (单位 cell pose count) | 09_density_envelope.md |

geometric vs literal 是核心 axis. geometric cut cert 含 region/partition/BFS
component 等几何对象 (用 bitset 编码), validator 重算几何 check. literal cut
cert 含 (group, pose) 对的 multiset, validator 验 multiset match. 两种 mode
互斥, family ↔ mode 锁定 (PROJECT_LOCK §3A invariant 3, `lifecycle.py:_FAMILY_MODE_MAP`).

9 个是 Phase 0 final 锁定的 (Gemini r26 GO). 不再加 / 不再删 / 不再改 mode.
Phase 1.2 实施 F5-F9, 不改这 9 个 list.

### 2.2 为什么 lifecycle 是 9 step

不是 7 step 也不是 11 step. 9 step 是不同 trust boundary 的最小拆分:

```
0. canonicalize     raw dict → canonical bytes (cert hash 确定性)
1. generate         oracle 产 cert + scope
2. minimize         literal-based deletion / QuickXplain (Step 2 defer Phase 1.1 P1.11)
3. serialize        Cut → JSON bytes
4. deserialize      JSON bytes → Cut (schema invariant 重检)
5. validate         独立重算 cert (oracle 不可信, validator 是 trust boundary)
6. attach-scope     6-step scope verify (source_digest / ghost / blocked / artifact / oracle / assumption)
7. evaluate         family-dispatch 验当前 state 是否仍 violate
8. apply-to-master  push 进 CP-SAT (Phase 1.3 P1.21 实施)
9. regression       re-validate on new replay state (Step 5 re-entry)
```

为啥 step 5 跟 step 7 必拆: step 5 是 oracle-time 重算 (cert 本身 sound), step
7 是 evaluator 重算 (当前 state 仍 violate). 这两个 trust boundary 不同 —
step 5 不通过 → cert 本身错 (quarantine), step 7 不通过 → cert 过期 (退场,
不 quarantine). 合并就丢这个区分.

为啥 step 6 必拆: source_digest / ghost / blocked / artifact / oracle /
assumption 6 个 sub-check 各有 fail-closed 语义. 任一漏验 = lifecycle 失控
(GPT v6 P0 反例正是 on_ghost_rect_changed 把 step 6 当全部验证, 漏了 step 7).

### 2.3 核心 invariants (PROJECT_LOCK §3A)

不能跨这些边界:

1. **family ↔ mode XOR** — literal-based vs geometric-based 互斥, 改一行 family 表也得跨
   spec/src/test 同步
2. **cut.scope + cert + literals XOR geometric_payload 必填** — __post_init__ 强制
3. **GHOST_AGNOSTIC sentinel** — 不能跟普通 ghost_id 混用, validator 必验
   scope.ghost_rect_id 是否真合法 (Step O P0 修)
4. **9 family list frozen** — 无 symmetry_lift (Phase 0 final), 含 F1-F9
5. **ASSUMPTION_VERIFIERS dispatch** — 必经 verifiers module, 不准 inline
6. **multiset eval 不看 slot index** — state_machine §5 anonymity, slot 是
   group 内 anonymous reorderable; 但 validator 内部 binding 阶段 slot
   必 resolve 到具体 pose (GPT v2 P0-2 修)
7. **source_digest 锁 data version** — 当前为 sha256 content hash，
   Phase 1.2 切真 hash; 锁定后 cross-session cert 才可信

### 2.4 adversarial soundness 假设

`[[adversarial-soundness-audit]]` memory 总结: validator audit 分两层. Layer 1
spec ↔ src ↔ data 接合 (Gemini r27-32 覆盖). Layer 2 adversarial — 假 cert
能 pass 吗 (GPT pro r1-r6 覆盖).

cut framework 默认 oracle **不可信** (oracle 可以是 stub / 外部 import / disk
load / 旧 schema). validator 是 trust boundary, 必须能 reject 任何不 sound 的
cert. 这导致 validator 比 oracle 重 (radon D 级), 这是 by design — Step J/L/
M/N/O 5 轮 audit 反复加 validator binding 都是 adversarial soundness 拉紧.

---


## 18. PROJECT_LOCK §3A 边界

后续重构不能跨这些边界 (per `PROJECT_LOCK.md` §3A):
- family ↔ mode XOR (literal vs geometric) 不可改
- **F8 mode 锁 geometric** (cert 可引用 power pole group/pose 上下文, lifecycle body 不走 literal multiset path — 改 mode 必先改 PROJECT_LOCK)
- cut.scope + cert + literals XOR geometric_payload 必填
- GHOST_AGNOSTIC sentinel 不能跟普通 ghost_id 混用 (Step O 加 validator 验)
- 9 family list frozen (无 symmetry_lift, 含 F1-F9)
- ASSUMPTION_VERIFIERS dispatch 必经 verifiers module, 不准 inline
- multiset eval slot anonymity (state_machine §5)
- source_digest 锁 data version (✅ Phase 1.1 exit hardening 真 sha256 落地)
- adversarial soundness — validator trust boundary, oracle 不可信
- **F9 area-only invariant** (Gemini math review meta-audit 2026-05-23): F9 generator 只接受 `area_capacity_overflow` witness, 拒绝 `routing_overflow` / `binding_overflow` / `pcr_cut_overflow`. F9 evaluator 必 area-based `sum(|pose_cells ∩ W|)`, 不是 instance count / origin-in-window / all-in-window
- **F6/F7 proof obligation 加严**: F6 Hall cut greedy 失败不能当不可行证明, validator 必重算 Hall violation witness; F7 hitting-set cut LP relax / greedy 只能 oracle hint, validator 必验安全下界或 dual cert
- **F9 strict inequality**: 等号不 cut, 只有 `cert_density > max_density` 才 cut

任何 §3A 边界改动必先 PROJECT_LOCK 更新 + 跨 spec / src / test 同步.

---

