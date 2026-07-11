# 18 — 环境变量 / 配置清单

> **现状 + 历史草案（2026-07-11）**：当前接口以源码读取点为准；下方 `EXACT_CUT_STORE_*` 名称只是未采用的历史提案。任何开关都不得绕过 supervisor、public publisher 或 owner gate。


cut framework 用 env 做 phase/feature toggle, 不用 config file (跟项目其他 EXACT_* env 一致, 避免新 config schema). 本节列当前 cut framework 自己 + 跟主流程 cut 相关 env 的 interaction.

### 19.1 cut framework 自身 env (现状)

| Env | 当前默认 | Phase 1.2 默认 | Phase 1.3 默认 | 用途 |
|---|---|---|---|---|
| `EXACT_FAMILY_VALIDATOR_STRICT` | `"1"` | `"1"` | `"1"` | strict gate: 未注册 family / dispatch 漏注册 → fail-closed。`"0"` 仅允许本地临时调试，不进生产 wrapper。 |
| `EXACT_F3_GENERATOR_ENABLED` | `"0"` | `"0"` (gated) | — | F3 port_exposure generator 开关（commit `c768806` 落地，default-disabled）。**(2026-06-04 补：早先此现状表漏列)** |
| `EXACT_F7_GENERATOR_ENABLED` | `"0"` | `"0"` (gated) | — | F7 generator 开关（default-disabled）。F8 已退役，`EXACT_F8_GENERATOR_ENABLED` 不再是有效接口。 |

### 19.2 当前 direct attach env 与未采用的历史提案

当前 direct bridge 使用：

| Env | 默认 | 用途 |
|---|---|---|
| `EXACT_CUT_FRAMEWORK_ATTACH` | unset/OFF | direct Step-8 bridge 总开关；在 certified unsafe map 中，certified 路径设置即 fail-closed |
| `EXACT_CUT_FRAMEWORK_ATTACH_BUDGET` | `2000` | active-cut attach 上限；仅接受正整数，非法值 fail-closed |

早期文档提出的 `EXACT_CUT_STORE_ENABLE`、`EXACT_CUT_STORE_SHADOW_ONLY`、`EXACT_CUT_STORE_TELEMETRY_PATH`、`EXACT_CUT_STORE_MAX_HELD_CUTS`、`EXACT_CUT_STORE_REPLAY_REJECT_KILL_PCT` **未成为当前接口**；引用时必须标为历史提案，不得当作可用 env。

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

