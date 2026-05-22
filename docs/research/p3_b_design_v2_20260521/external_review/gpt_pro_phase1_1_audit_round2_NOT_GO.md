# GPT pro Phase 1.1 audit round 2 — verdict NOT GO

第二次 GPT pro audit. 同 input pkg + 同 prompt (chat 给), 不同 session.

**两次 verdict 一致 NOT GO**, F1 + F3 都 P0. round 2 在 round 1 基础上加了
精确数字和 新 risk:

## Round 2 vs Round 1 差异

### 同样 P0 (两次都 catch)

1. **F1 demand_R 不满足 P(g) ⊆ R**
2. **F3 validator 不绑 cert ↔ literal**

### Round 2 新增 / 加深的 finding

1. **`python -O` 删 F3 assert 风险** (round 1 没明确实测):
   - `port_exposure.py:127`: `assert cut.literals is not None and len(cut.literals) >= 2`
   - 普通 Python: 一元 literal → schema_err ✓
   - `python -O` 模式: assert 被删 → 一元 literal validator 返 `ok` ✗
   - certified solver production 不能接受
   - 14 bandit B101 assert_used 中此条最严

2. **F1 boundary pool 精确扫描数字**:
   - total boundary_storage_port poses: 54
   - wholly inside implemented union: 40
   - wholly outside implemented union: 14
   - mixed (partial inside): 0
   - all boundary unique occupied cells: 162
   - inside union cells: 120
   - outside union cells: 42

3. **F3 错配反例更精确**:
   - cert blocker: `viewer::mfg_crusher_source_013`
   - cut.literals 错放: `viewer::mfg_crusher_source_014` (同 group 不同 pose)
   - validator: `ok` + evaluator `True`
   - 把"前方被 p13 挡"错误变成"选了 p14 就禁"的 cut

4. **direction encoding N/S/E/W 真数据覆盖统计**:
   - 273 poses / 530 ports total
   - N=273 / S=257 / E=0 / W=0
   - 旧 axis-swapped encoding: 476/530 front 落自身 occupied (反向验证)
   - 当前 N=(0,-1)/S=(0,1) 强 verify pass, 但 E/W 没真数据 coverage —
     不能说 "universal", 只能说 "没找到 counter-example"

5. **F4 BFS vs Tarjan 决定 OK 但范围限制**:
   - 当前 F4 spec 是 free-cell reachability, BFS 4-conn sound
   - **若未来 belt routing 改有向流, BFS 不能复用** — F8/Phase 1.5+ 注意
     不要 inherit 此 helper

6. **HR5 GHOST_AGNOSTIC invalidate 是最先爆 high-risk**:
   - `store.py:212-215` 注释自承 GHOST_AGNOSTIC cut 不入 ghost watcher,
     blocked/exterior watcher deferred Phase 1.2+
   - F1 这种 GHOST_AGNOSTIC cut 的 exterior_blocks 变化 store 层没自动 trigger
     replay — 只靠 step_6 attach-scope hash check 静态比对
   - 任何 exterior_blocks 改动路径无显式 replay → 旧 cut 继续 active

7. **pytest-randomly + thinc reseed 兼容性 (sandbox-local)**:
   - 包内含 pytest_randomly 4.1.0, 但 thinc reseed range `Seed must be between
     0 and 2**32 - 1` 拒
   - `pytest -p no:randomly` 跑 → 139 PASS
   - 不是项目断言失败, 是 sandbox env conflict
   - production CI 没此问题 (我没装 thinc), 但 GPT 包内 sandbox 撞

8. **F2/F3/F4 spec drift 具体 line cite**:
   - F2: `02_cutset.md:65-77` cert schema vs src 缺 cut_edges 集合 verify
   - F2: `02_cutset.md:150-159` validator pseudocode 要 max-flow witness
   - F3: `03_port_exposure.md:41-43` 仍写 up/down/left/right
   - F3: `03_port_exposure.md:46-48,144-147` active_port_witness 要求
   - F4: `04_component_reach.md:141-150` cert bitset + separator 要求

## 必修 (GPT round 2 列 7 项, vs round 1 6 项)

合并 round 1 6 项 + round 2 新加:

1. F1 demand_R 改成真 P(g) ⊆ R (用 GroupState.pose_domain + candidate_placements.
   occupied_cells, 验所有 pose 都 ⊆ R)
2. F1 加真数据 regression (14 outside pose 存在时 不得 emit demand_R=138)
3. F3 validator 绑 cert ↔ literals: multiset 精确等于 cert
   {(facility_group, facility_pose_id), (blocking_group, blocking_pose_id)}
4. F3 所有 schema assert → 显式 fail-closed (`if ... return schema_err`),
   不依赖 assert (生产 `python -O` 失效)
5. strict registration gate: Phase 1.2 前 F1-F9 全 family 必须注册,
   `EXACT_FAMILY_VALIDATOR_STRICT=1` 下未注册 fail-closed
6. GHOST_AGNOSTIC invalidation watcher 实施 (blocked/exterior change 显式
   trigger replay, 不能只靠注释)
7. spec docs 跟 src align: state_machine_v2 PoseId / cut_lifecycle_v2 9
   family list / F2/F3/F4 family spec

## 跟 round 1 verdict 一致点

两次都 binary NOT GO, 都点名 F1 + F3 P0, 都列 spec drift, 都列 mypy strict 29
errors. round 2 比 round 1 数字更精确 (40+14+0 / 120+42 / 530 port / N=273 S=257)
但 verdict 不变.

## 取证级 evidence

[[external-review-reproducibility]]: 同 prompt 跑两次 finding 列表通常不一定一致.
这次两次 重叠 critical (F1 + F3) — 高 confidence signal, 不是 GPT 一次随机抽
中. F2/F4 round 1 标 critical, round 2 重新归 "cert 完整性弱于 spec / 配套 必修",
但本质同 — validator 不够严密.

## 我自查 verify (commit 868bef7)

全 8 个 round 2 finding 100% 真, 0 误报:

| Finding | Verify |
|---|---|
| `python -O` 删 F3 assert (port_exposure.py:127) | ✅ 实测 `.venv/bin/python -O` 跑 1-literal cut, validator `kind=ok` (正常模式 schema_err 不通过) |
| boundary 池 40 inside / 14 outside / 0 mixed / 162 unique cells / 120 in / 42 out | ✅ 跑 candidate_placements scan, 数字精确 match |
| F3 同 group p013 cert + p014 literal 仍 ok | ✅ 复现 (round 1 用 不同 group, round 2 同 group 更严) |
| direction 530 ports N=273 S=257 E=0 W=0 | ✅ 跑 candidate_placements 全 273 pose, axis-swapped 476/530 落 occupied (强证当前 0 落) |
| F3 spec line 42 `Literal["up", "down", "left", "right"]` | ✅ grep 真在 |
| F4 spec line 141/144/145/148 要 bitset/separator/assumption | ✅ src 都没实施 |
| F2 spec line 70-76 cut_edges/witness_blob/max_flow | ✅ src `validate_cutset` 只 count edges, 没 cut_edges Set verify, 没 max_flow witness |
| cut_lifecycle_v2.md line 227 `PoseId = int` + 多处 symmetry_lift | ✅ src 已改 str + 9 family (无 symmetry_lift), spec doc drift |

最严重: `python -O` 删 assert 是 production-critical. certified solver 减 1% perf 跑 -O 是常见 path. assert 失效后 schema check 不存在, 一元 literal cut 全通过假证.
