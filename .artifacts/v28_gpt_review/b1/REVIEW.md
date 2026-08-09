# Phase 1.2 spike close 严格闭关审查 — v28 外部审查结果

审查对象: `phase1_2_spike_review_v28.zip`

## 0. Verdict

**Verdict: (b) 当前证据不足，不能关闭 Phase 1.2；需先修复 F9 与 F6 两个 soundness blocker，再重新跑 cut tests / replay / sizing gate。**

Sizing gate 的核心数字可复现，F9 single-group invariant 对当前代码成立。阻塞点是 soundness：当前包仍存在两个与 F7 `pole_radius` 同源的“cert 内数值字段未被 source-of-truth / replayable proof 约束”的 fail-open 路径。

| ID | Severity | Family | 结论 |
|---|---:|---|---|
| S1 | HIGH / BLOCKER | F9 `density_envelope` | `max_allowed_area` 只校验 `<= safe_ub`，没有证明它是安全上界；伪造更小 K 可错误剪掉合法布局。 |
| S2 | HIGH / BLOCKER | F6 `shape_packing_hall` | `region_demand` 只做范围校验，未证明该区域确实被强制放置 d 个实例；伪造 d 可错误剪掉“全放另一边”的合法布局。 |
| D1 | LOW | docs / spike mirror | `CLAUDE.md` 仍写 v22/CC memory，`spike_prod_scale_runner.py` 仍会生成 v20 package 文案。 |

## 1. Repro summary

原包 SHA256 与用户给定值一致：`c00a957c73f1a05b532de73451aff8676fc0e3303dfc453bd62630e4b06e5253`。

原包：
- `python -m pytest src/tests/cuts -q` → **418 passed**
- `python -O -m pytest src/tests/cuts -q` → **418 passed**
- `cd project/code_context && sha256sum -c SHA256SUMS.spike_code.txt` → **11/11 OK**

Sizing gate 复现关键数字：
- type-pool total poses = **81,795**
- concrete/group-expanded proxy = **325,747**
- F9 single-group max = **784**
- F9 same-template proxy max = **4,608**
- F9 all-manufacturing stress max = **11,644**
- F4 group-expanded max = **20,157**
- OR-Tools linear bytes/term ≈ **4.03**
- OR-Tools BoolOr bytes/term ≈ **10.01**

## 2. S1 — F9 `max_allowed_area` tight-bound fail-open

当前 F9 validator 验证的是：

```text
0 <= K <= safe_ub
exists witness A: area_g(A, W) > K
```

但 master cut `area_g(W) <= K` 需要证明的是：

```text
for all legal layouts L: area_g(L, W) <= K
```

`exists A area(A)>K` 不推出 `forall L area(L)<=K`；这是量词方向错误。

形式化有限反例：

1. 取 window `W` 含单元格 `c`，无 ghost/exterior，所以 `safe_ub = |W| >= 1`。
2. group `g` demand=1，pose domain 含合法 pose `p`，`p` 占用 `c`。
3. 伪 cert 设 `max_allowed_area=0`，witness 为 `[(g,p)]`。
4. 当前 validator 重算 witness overlap=1，满足 `1 > 0`，且 `0 <= safe_ub`，因此接受。
5. 合法布局 `L={g at p}` 满足 `area_g(L,W)=1`，却被 cut `area_g(W)<=0` 剪掉。

因此当前 validator 可接受 false-positive cut。补丁 `0001` 在没有 replayable tight-bound proof/oracle verifier 前拒绝 `max_allowed_area < static safe_ub`，保守 fail-closed。

## 3. S2 — F6 `region_demand` 条件前提 fail-open

F6 当前只证明：

```text
total_packable(region) < cert.region_demand
```

但没有证明 `cert.region_demand` 是 source-of-truth 强制事实。对 `left_or_bottom_boundary` group，单边需求不是 canonical rule；需求可全放另一条 baseline。

形式化有限反例：

1. group `g` demand=2，规则为 `left_or_bottom_boundary`。
2. left_baseline 容量为 0；bottom_baseline 可容纳 2。
3. 伪 cert 选 `region_kind=left_baseline`，`region_demand=1`，`group_demand=2`。
4. 当前范围校验通过，partition 重算也显示 `0 < 1`。
5. 合法布局把两个实例都放 bottom；它要求 left 放 0 个。无条件几何 F6 cut 会错误剪掉它。

补丁 `0002` 增加 `_validate_region_demand_source_of_truth`：只有当 group 的所有 pose_domain pose 都完全落在 cert region 内、且 `region_demand == group_demand` 时接受。若 P1.5/P1.3A 要用当前 master solution 的 per-region count，必须升级为 conditional/literal proof schema。

## 4. 非 finding

- F1：`cap_R`、`demand_R`、`cells_per_pose` 均从 state/source-of-truth 重算。
- F2：`cut_size`、cut edges、commodity demand/routes 均重算/核对。
- F3：port/blocker 绑定从 `cell_owner` 与 `candidate_placements` 核对。
- F4：component BFS 与 commodity route registry 重算/核对。
- F5：validator re-query oracle adapter，不是单纯信任 cert。
- F7：`_validate_pole_radius_sot` 已存在，半径与 canonical source-of-truth 对齐。
- F8：`pole_jump_radius` 与 canonical power radius 对齐，ghost-only disconnect 重算。
- F9 single-group invariant：validator 拒绝 witness group != cert group，evaluator 只数 cert group，watcher 只挂 cert group；因此当前单条 F9 cut 的 784 single-group vector 界成立。11,644 是 stress proxy，不是当前 per-cut bound。

## 5. Phase-boundary decision

选择 **(b) spike 证据不足**。关闭 Phase 1.2 至少需要：

1. 应用 `0001` 或实现等价 F9 replayable tight-bound verifier。
2. 应用 `0002` 或实现等价 F6 conditional/literal region-demand proof schema。
3. 应用 `0003` 或等价 doc-currency 修复。
4. 重新跑 cut tests、`-O` tests、code_context SHA manifest、sizing gate。
5. 若不 quarantine F9/F6，而是恢复 tight cut，需要同步 PROJECT_LOCK / proof schema / tests。

## 6. Patch verification

在 clean package 上三补丁 `patch -p1` dry-run 与实际 apply 均通过；apply 后：

```text
python -m pytest src/tests/cuts -q
= 419 passed

cd code_context && sha256sum -c SHA256SUMS.spike_code.txt
= 11/11 OK
```

测试数从 418 到 419，是因为 F6 增加了一个 explicit red fixture：未证明的 `region_demand` override 被拒绝。
