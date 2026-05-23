# 18 — 环境变量 / 配置清单

cut framework 用 env 做 phase/feature toggle, 不用 config file (跟项目其他 EXACT_* env 一致, 避免新 config schema). 本节列当前 cut framework 自己 + 跟主流程 cut 相关 env 的 interaction.

### 19.1 cut framework 自身 env (现状)

| Env | 当前默认 | Phase 1.2 默认 | Phase 1.3 默认 | 用途 |
|---|---|---|---|---|
| `EXACT_FAMILY_VALIDATOR_STRICT` | `"0"` | `"1"` (§10.1) | `"1"` | strict gate: 未注册 family / dispatch 漏注册 → fail-closed (replay HOLD). `"0"` 时 unknown family 走 schema_err 但不 hard-fail (Phase 1.1 调试模式). |

### 19.2 Phase 1.3 propagator 集成预留 env (实施时定名)

下面 env 在 §12 / §13 实施时加, 当前未实施. 命名前缀按项目惯例 `EXACT_CUT_STORE_*`:

| Env (拟) | 默认 | 用途 |
|---|---|---|
| `EXACT_CUT_STORE_ENABLE` | `"0"` | 总开关. OFF 时 master.solve 不接 cut, 框架仅 unit test 跑 (Phase 1.3 first commit) |
| `EXACT_CUT_STORE_SHADOW_ONLY` | `"0"` | shadow 模式: framework run 但 cut 不真 attach master, 仅 telemetry (24h shadow trial 用, §14.3) |
| `EXACT_CUT_STORE_TELEMETRY_PATH` | (unset) | telemetry jsonl 落盘路径. unset 时不落盘 |
| `EXACT_CUT_STORE_MAX_HELD_CUTS` | `"10000"` | held queue 上限. 超 → 拒新 cut 入 held (LRU evict 暂不做, 简单 cap) |
| `EXACT_CUT_STORE_REPLAY_REJECT_KILL_PCT` | `"5.0"` | replay reject rate 超此 % → 整 candidate trial abort (§14.3 revert criterion) |

最终名以 §13 实施时 commit 为准, 此表是 placeholder; 加 env 时同步更新本节.

### 19.3 跟主流程 cut/master 相关 env (cut framework 不直接读, 但 interaction matters)

| Env | 默认 | 跟 cut framework 关系 |
|---|---|---|
| `EXACT_USE_POSE_BOOL_MASTER` | OFF | B1 pose-bool master paradigm. cut framework 不绑 master 形态, OFF/ON 均工作 (Phase 1.3 接进时验) |
| `EXACT_B1_PATCH_ROUTING_CORE` | OFF | PCR-CUT (Path 14). 当前是独立 cut 生成路径 (env-gated front_blocked branch), 跟 B Design v2 cut store 不直接共享. Phase 1.5+ 可能 merge (TBD) |
| `EXACT_B1_PATCH_ROUTING_CORE_TOP_K` | `"3"` | PCR-CUT 同上 |
| `EXACT_B1_PATCH_ROUTING_CORE_SECONDS` | `"10"` | PCR-CUT 同上 |
| `EXACT_B1_PATCH_ROUTING_CORE_PER_PATCH_SECONDS` | `"5"` | PCR-CUT 同上 |
| `EXACT_B1_PATCH_ROUTING_CORE_MAX_CELLS` | `"900"` | PCR-CUT 同上 |
| `EXACT_B1_PATCH_ROUTING_CORE_QX_CAP` | `"32"` | PCR-CUT 同上 |
| `EXACT_B1_ABSTRACT_ROUTING_LAYER` | OFF | L2 abstract routing (SAC-Hull). cut framework 独立 |
| `EXACT_B1_SEPARATOR_HULL` | OFF | SAC-Hull L1 static separator. cut framework 独立 |
| `EXACT_B1_SEPARATOR_HULL_DYNAMIC` | OFF | SAC-Hull L2 dynamic separator. cut framework 独立 |
| `EXACT_B1_D2_COMMODITY_FLOW` | OFF | D2 Path 17 (paradigm 死). cut framework 独立 |
| `EXACT_B1_ROUTING_AWARE_BINDING` | OFF | routing-aware binding. 跟 F2/F4 commodity registry 可能交互 (Phase 1.5+ §13.1 决) |
| `EXACT_MASTER_GHOST_ANCHOR_FILTER` | (unset) | ghost anchor 限缩. 跟 cut.scope GHOST_AGNOSTIC 不冲突 (前者限 master, 后者限 cut applicability) |
| `EXACT_OUTER_SKIP_UNKNOWN` | OFF | outer search skip UNKNOWN candidate. 跟 cut framework 不直接交互 |

### 19.4 toggle 政策

- 任意 cut framework env 改 default 必走 §14.3 phase-roll (src commit, 不准 hot env override 绕)
- Phase 1.2/1.3 之前不准把 `EXACT_FAMILY_VALIDATOR_STRICT="0"` permanently 配进生产 wrapper (`scripts/run_campaign_*.sh`) — strict OFF 仅本地调试 / 测试时临时 export, 不入生产
- env 冲突检测: implementer 加新 env 时必在 spec / plan 19.1 表加一行 (避免散落)

---

