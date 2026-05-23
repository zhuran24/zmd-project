# 12 — GO 标准 / 验收准则

每段 done 怎么定义. 不只 "代码改完 commit pass test", 而是要过 reviewer audit.

### 8.1 Phase 1.2 P1.11 入门 GO

7 项 factual fix 全 land:
1. strict gate default ON
2. spec drift 7 处全清 (PoseId / family list / F3 direction / F1 region_kind /
   F2 cert schema / F4 commodity_id / source_digest spec)
3. source_digest 真 hash
4. ghost_rect tuple 语义 lock + 非方形 fixture
5. mypy strict 37 errors → 0 (typing hygiene 收尾)
6. radon D(27)/D(24)/D(23) → C(15) 或以下 (helper 拆)
7. `evaluate_literal_port_exposure` 决定 (删 or 接 dispatch)

验收:
- 172+ cuts test pass (现 172, P1.11 入门后 +5-10)
- ruff/mypy/vulture/bandit/radon 全 clean
- GPT pro v8 audit 收 GO 或最多 P1 finding (不再 P0)
- Gemini cross-check round 36+ 通过

### 8.2 Phase 1.2 P1.11-P1.15 (F5-F9 实施) GO

5 family 各自完整:
- validator + evaluator + oracle (oracle 可 stub)
- ≥ 10 unit test (sound + ≥ 3 attack 反例 + schema_err + adversarial scope)
- spec ↔ src ↔ 真数据 三层 align
- 每 family Gemini cross-check 通过
- 跨 family invariant test (e.g. F5 接 lifecycle step 2 minimize, F6 跟 F1 region 重叠 case, F7 跟 F3 port 重叠 case, F8 复用 F4 BFS helper, F9 跟 F6 density)
- F5-F9 全 register FAMILY_VALIDATORS, strict gate ON

验收:
- 总 cuts test ~250+ (172 baseline + 5 family × 10-15 each)
- 大节点 GPT pro batch audit 通过 (整 Phase 1.2 vs 单 family)
- production smoke 真数据 F5-F9 oracle 跑通 (各 oracle 真 emit cut 或合理
  fail-closed)
- 跟 PROJECT_LOCK §3A 不冲突 (family list 仍 9 个, mode 不变)

### 8.3 Phase 1.3 P1.21 (CP-SAT propagator 集成) GO

- step_8_apply_to_master 真接 master CP-SAT (env flag `EXACT_B_DESIGN_V2=1`)
- lazy → hard constraint 转化 sound (cut attach 后 master state 跟 cut violate
  一致)
- 168h smoke (24h 短跑 subset) 真跑 prune 减 search tree (跟 baseline 比节点
  数 / 时间)
- hot path perf 优化:
  - json.loads cache on Cut (避 evaluator 反复 parse)
  - F4 BFS incremental connectivity (替 O(|Grid|) 全图 BFS)
  - by_exterior_watcher 实施 (减 evaluator 调用频次)
- thread-safe 验证 (multiprocess.spawn worker 各 cache 独立 + GIL-safe)

验收:
- 24h smoke 比 Phase 3B repair5 baseline prune ratio improve ≥ 10%
- propagator 10K calls/sec scale evaluator latency ≤ 100 µs / call
- 真 168h campaign 跑通至少 1 个 candidate full search (不只 timeout)
- GPT pro audit Phase 1.3 整 phase 通过

### 8.4 Phase 1.5+ (production integration) GO

- commodity registry production inject 路径 unique builder (一函数从真 data
  build BState)
- 各 family oracle 真实施 (不再 stub `return []`)
- F3 active_port_witness verify
- F2 max_flow_LP algebraic witness
- F4 commodity registry 改 route_id 级别 schema (支持同 commodity 多 route)
- 168h 真 campaign 跑通 + 比 baseline (Phase 3B repair5 without cut framework)
  收敛 ≥ 30%

验收:
- 真 168h campaign 1+ candidate 真 OPTIMAL (不 timeout 不 UNKNOWN)
- GPT pro batch audit Phase 1.5 production GO
- 跟 Phase 3A delivery (r20260416) 衔接验证

---

