---
name: gpt-anchor-slicing-proposal
description: "2026-05-14 GPT-5.5 Pro 对 v5 RAM 瓶颈包的方案 — ghost-anchor slicing (env-gated disjunctive decomposition); v1/v2 已发包但链接过期下载不下来, v3 待用户压缩后发"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

**2026-05-14 GPT-5.5 Pro 对 v5 review 包的答复**: ghost-anchor slicing 方案,数学 sound,工程合理,但 RAM 实际效果未验证.

## 方案核心 (用人话)

70x70 一个 candidate (e.g. 42x32) 有 ~1131 个 ghost anchor. 现在主线把这 1131 个 anchor **一次性塞进同一个 CP-SAT master**, 每个 anchor 1 个 u_var + 2 个 optional interval, 全跟 266 个 mandatory facility intervals 一起进 NoOverlap2D, 单 candidate 就吃 28-30 GB.

GPT 方案: env-gated 拆成 1131 次 small master, **每次只 build 1 个 anchor 的 ghost overlay**, 跑完丢, 跑下一个. proof 基础:
- 一个 anchor solve 出 OPTIMAL → 整 candidate certified
- 所有 anchor 证 INFEASIBLE → 整 candidate infeasible
- 部分跑 (debug cap 截断) → **必须返 UNKNOWN, 不能伪造 INFEASIBLE**

数学 sound (disjunctive decomposition), PROJECT_LOCK 兼容 (env-gated default off, 没引 exploratory caps, 没改 max_lex, 没改 schema).

## GPT 的实现 (v2 包内容, 18 MB zip)

修改文件:
- `src/models/master_model.py` — 加 `ghost_anchor_subset` init 参数 + `_normalize_ghost_anchor_subset` static method + `_iter_ghost_anchor_positions` + `_ghost_anchor_subset_stats`. `_add_ghost_rect_constraints` 改成用 subset 过滤.
- `src/models/exact_coordinate_master.py` — `_add_ghost_constraints` 同样用 owner 过滤
- `src/search/benders_loop.py` — 加 `_run_benders_for_ghost_rect_by_anchor_slices` 函数 (~700 行新代码), `EXACT_GHOST_ANCHOR_SLICING=1` + `EXACT_GHOST_ANCHOR_SLICE_MAX_ANCHORS=N` env. 在 `run_benders_for_ghost_rect` 入口若 env on 转 slicing path.
- 新 test `src/tests/test_ghost_anchor_slicing.py` — 5 个新 test 都过
- PROJECT_LOCK.md / FILE_STATUS.md / CHANGELOG.md / specs/11 / docs/ghost_anchor_slicing.md 同步更新

GPT 自己跑过的 validation:
- `python -m py_compile`: OK
- 新 test 5/5 pass
- 相关回归 test 11/11 pass (cut_condition_lits + replay_lifecycle + area_precheck)
- patch apply 干净 (`git apply --check` on fresh extraction)
- **但 GPT sandbox 4 GB RAM 跑不了真 main.py, 没验证 RAM 真减了多少**

## v1 vs v2 区别

- v1 (zmd_anchor_slice_patch.zip): 提了 per-anchor resume manifest + cut condition_set fallback resolver (anchor idx 重编号 → 按 `ghost_anchor::(x,y)` 坐标 fallback). 链接过期没下载.
- v2 (zmd_ghost_anchor_slicing_patch.zip): 精简版本, **没有 resume manifest**. 意味 168h 中途挂了, anchor 从 0 重跑, 不利于真用满 168h budget. 链接也过期没下载.
- **v3 第一次 transcript** (commit `91eec91`, zip SHA256 `b54ac3b6...` 已过期):
  纯补丁交付; 用户 prompt 只 ask "再给一个补丁包".
  - 完整项目包结构: `code.tar.xz` + `patches/` + `docs/` + `audit_logs/` + `meta/` + `bin/`
  - 基础 ghost-anchor slicing 实现 (master_model / exact_coordinate_master / benders_loop)
  - **2 个 env**: `EXACT_MASTER_GHOST_ANCHOR_SLICE_MODE` + `EXACT_MASTER_GHOST_ANCHOR_SLICE_MAX_ANCHORS`
  - **没有 resume manifest** (跟 v2 一致, 168h 中途挂了 anchor 从 0 重跑)
  - 沙盒测试 5 套全 pass: anchor-sliced 10 + cut lifecycle 10 + master_model 226 + dynamic subset 344 + preflight core 108
  - 静态: compileall / ruff / mypy core / bandit 全 pass
  - 中途 `/mnt/data/work_zmd` 沙盒重置一次, 重启到 `/mnt/data/work_zmd_cur`

- **v3 第二次 transcript** (commit `4a34d74` "Phase3B anchor-sliced exact proof with resume", zip SHA256 `4b051bcc5703156877c34f616fbddd670c3865199a7daf1029735139d1e9fd34` 也已过期):
  用户 prompt 明确 ask 两件事 + 第二次大改:
  - 用户原话: "请仔细检查一下我这个项目任何可能存在的漏洞和问题, 进行全量的动态审查和静态审查"
  - 用户原话: "最后给出修复后的, 加上之前的丢失掉的补丁, 以及加上了per-anchor resume manifest的完整项目包"
  - 用户原话: "里面记得放上这三个内容(问题、之前丢掉的补丁、还有per-anchor resume manifest)的相应文档"

  **第二次比第一次新增**:

  1. **per-anchor resume manifest 全套** (用户点的):
     - 默认 `data/checkpoints/anchor_slice_manifests/<candidate_key>.json`
     - 从 2 个 env 扩到 4 个: 新增 `EXACT_MASTER_GHOST_ANCHOR_SLICE_RESUME` (default on) + `EXACT_MASTER_GHOST_ANCHOR_SLICE_MANIFEST_PATH` (可指向文件或目录)
     - identity guard 签名: schema_version + mode + partition_kind=`ghost_anchor_partition_v1` + candidate_key + ghost_rect + grid + artifact_hashes + master_search_profile + total_anchor_count; mismatch 整 manifest invalidate, 记 `invalidated_previous_manifest_reason`
     - atomic write: `os.replace(tmp → path)` + `indent=2` + `sort_keys`
     - 状态机: `CERTIFIED` / `INFEASIBLE` / `EXCLUDED_BY_BOUNDARY_PORT_PRECHECK` 为 terminal; 非 terminal entry 下次重试
     - entry validation 严格: original_anchor_idx + status + terminal + anchor x/y + CERTIFIED 必须有 solution mapping + proof_summary 必须 mapping, 不通过整 entry 丢
     - 父 INFEASIBLE 严格条件: `complete_partition == true && truncated_by_env_cap == false` (任一不满足返 UNPROVEN)
     - boundary excluded anchors 立即 atomic-write 到 manifest (不是 evaluated 完才写)
     - resume 时优先扫 manifest 找 CERTIFIED → 直接返回不重跑

  2. **全量审查 + 沙盒能修的修** (用户点的):
     - 跑过的工具: compileall / ruff / mypy (两次, 含 `--explicit-package-bases`) / bandit / radon (cc+mi) / vulture / targeted pytest 251 pass / preflight 11 pass / git diff check / production_readiness_gate
     - **GPT 没单独列"项目问题列表"** — finding 全是工具 output (日志在 audit_logs/)
     - **实际修了 3 类**:
       - 把自己 patch 里新加的 broad `except Exception` 全缩到具体异常组合 (TypeError/ValueError/OSError/JSONDecodeError/AttributeError/KeyError/IndexError) → bandit Low 69 → 68
       - vulture 抓到 `cut_replay_condition_skipped` 没引用 → 加进 proof_summary 两处公开
       - `FILE_STATUS.md` CRLF + trailing whitespace 整理 → `git diff --check` pass
     - **没碰的**: preexisting typing debt (OR-Tools 没 stubs / `IntVar | None` 没 narrowing / 重定义 / interchange 模块 union-attr 等 110+ mypy errors) + preexisting 68 low bandit (broad telemetry except) + vulture 大量 false-positive unused future-scope helpers. 合理 — 不属于 patch scope.

  3. **架构修复细节** (第一次没的):
     - `_selected_ghost_anchor` 改为返回 **original_anchor_idx** (不是 local rect_idx) — 新生成的 ghost-conditioned power cut 持久化的也是原始 anchor 编号, 跨 slice 安全
     - candidate_key suffix `__anchor_N` for hint persistence 跨 slice 隔离
     - readiness gate **slice-aware**: profile=anchor-sliced / 18 GB default vs all-anchor 30 GB + env `EXACT_MASTER_GHOST_ANCHOR_SLICE_PEAK_RSS_GIB` 可校准
     - `main.py` forward `--parallel-processes` 到 `EXACT_PARALLEL_PROCESSES` env, readiness gate 才读得到
     - cut replay resolver slice-overlay 兼容: full overlay 走直接 rect_idx; sliced overlay 用 `(coord, original_anchor_idx)` 唯一匹配 fail-closed fallback

  4. **代码触达点**:
     - `master_model.from_exact_core` / `_add_ghost_rect_constraints` 加 `ghost_anchor_filter_indices: Optional[Collection[int]]` + `original_anchor_idx` 元数据 + build_stats 记 `sliced` / `filtered_original_anchor_indices` / `total_unfiltered_placements`
     - `exact_coordinate_master._add_ghost_constraints` 同 filter, 空 filter 时 `0 == 1` 立即 infeasible cut
     - `benders_loop.py` 加 schema/partition_kind 常量 + helpers (`_anchor_slice_manifest_path` / `_anchor_slice_manifest_signature` / `_load_anchor_slice_manifest` / `_save_anchor_slice_manifest` / `_anchor_slice_entry_is_valid_for_domain` / `_anchor_slice_status_is_terminal` / `_anchor_slice_status_closes_infeasible_partition`) + 大函数 `_run_anchor_sliced_benders_for_ghost_rect` + `_anchor_sliced_proof_summary_from_parts`
     - 新 test `test_anchor_slice_resume_manifest.py` (signature mismatch + cap-limited resume)
     - 增量 test `test_benders_cut_replay_condition_lifecycle.py` (sliced overlay remap) + `test_production_readiness_gate_oom.py` (anchor-sliced profile)

  5. **交付包结构更完整** (第一次没的):
     - `package_build_info.json` (commit hash + 测试摘要)
     - `audit_logs/` 全套审查日志 (compileall / ruff / mypy / bandit / radon / vulture / pytest / preflight / git_diff / production_readiness)
     - `SHA256SUMS.txt` + `MANIFEST.txt` 可重现性
     - 三份主题文档: 问题与审查摘要 / anchor-sliced proof / per-anchor resume manifest

  6. **沙盒环境不稳**: `/mnt/data` 被重置 2 次, GPT 重启沙盒 3 次 (work_zmd_cur → work_build), 最终在 `/mnt/data/work_build/repo` 完成 commit

  7. **沙盒做不了诚实标 attempted_not_completed**:
     - full pytest -q: 3% 进度手动终止 (沙盒卡)
     - production_readiness_gate slice mode: 沙盒非 Arch + 缺 `.venv` + RAM 3 GB → BLOCKED (但 `profile=anchor-sliced` 字段已生效)

  8. **GPT 主动承认仍未验证的** (跟 v2/第一次一致 caveat):
     - RAM 实际减多少**没人本机量过** — 大头若 facility 部分则只减 20-40%, 不是 50%+
     - Wall-time 可能涨 (per-anchor solve overhead × N)
     - Slice cuts 不跨 anchor 复用, LBBD 信息浪费

## 我对这方案的评价 (honest, 不是 oversell)

**好处**:
- 数学 sound, proof basis 标准 disjunctive decomposition
- env-gated default off, 不破坏现有 path
- PROJECT_LOCK 兼容 (cuts 不跨 anchor promote 避免 over-prune)
- 工程实现合理, regression test 都过

**关键 caveat (未验证, 必须本地实测)**:
1. **RAM 减多少不知道**. 28-30 GB 大头是 facility 部分 (266 设施 × signature buckets × LP relaxation) 还是 ghost overlay 部分 (1131 anchor × per-anchor tightening constraints)? slicing **只减 ghost 那块**. 如果大头是 facility, 这方案只减 20-40%, 不是 50%+. 但即使 30% 减, 30 GB → ~20 GB, 可能足够让 -p 2 跑得动 (20 × 2 + 8 host = 48 GB 临界).
2. **Wall-time 代价**. 单 candidate 跑 N 次 small solve 而不是 1 次大 solve. boundary-port precheck 会先砍大部分 anchor (70x19 例子 52/52 全砍), 但 42x32 1131 anchor 真 survivor 多少决定 168h budget 够不够.
3. **Slice cuts 不跨 anchor 复用**. 每个 slice 重新学 binding/routing infeasibility, LBBD 信息浪费. v1 有 resume manifest 跨 OOM 不丢, v2 砍掉了.

## 下载问题

ChatGPT 临时 artifact 链接老过期是 OpenAI 已知问题 (跟 `feedback_external_review_reproducibility.md` 那条对应). **整个 patch 的 unified diff 在聊天文本里**, zip 只是同一份打包. 不用纠结下载, patch 内容能从聊天 reconstruct.

## 下一步路径选择

收到 v3 后两条:

**A. 自己写最小版本**: 不要 reconstruct GPT 4500+ 行完整 patch (他塞了一堆 telemetry/proof_summary 装饰). 自己写最小核心:
- `MasterPlacementModel.__init__` 加 `ghost_anchor_subset` 参数
- `_add_ghost_rect_constraints` 用 subset 过滤
- outer_search 加 env hook + 逐 anchor 跑
- ~50-100 行核心改动 + 1 个 test
- 立刻本地实测 RAM (fresh start -p 1 + env on, 跑 5-10 min RSS curve)
- 30-60 min 出 RAM 真减多少的答案

**B. Reconstruct GPT 完整 patch**: 文本全在聊天里, paste + escape 抠出来. 工作量 1-2h. 拿到他的 telemetry/proof_summary 装饰 + test 套. 但同样最后要本地实测 RAM.

**优先 A** — 实测数据比工程装饰重要. 如果 A 实测 RAM 真减到 18-22 GB / candidate, 再 backport GPT v2/v3 的 production 装饰. 如果 A 实测没减, 写 memory + 找下一条路径.

## How to apply (等 v3 决策后)

跟 [[p1-24-oom-blocked]] 链: 那条记软方向全死, 真路径需要算法重构 / 换 solver. GPT slicing 是 "算法重构" 路径里的最轻量版本 (不动 solver, 不改 schema, 只切 disjunction), 工作量比"换 solver / 改 LBBD 切更细子问题"小一个数量级. 值得试.

## 2026-05-15 A 方案 PoC 实测 — RAM 减不够, KILL

**land 的 hook**:
- `MasterPlacementModel.__init__` + `from_exact_core` 加 `ghost_anchor_filter: Optional[Collection[Tuple[int,int]]] = None`
- `_add_ghost_rect_constraints` (legacy) + `ExactCoordinateMasterPlacementDelegate._add_ghost_constraints` 在 anchor inner loop 加 filter skip + build_stats `anchor_filter_applied`/`anchor_filter_skipped`
- `benders_loop.py` 加 `EXACT_MASTER_GHOST_ANCHOR_FILTER` env (format `"x1,y1;x2,y2;..."`) + `_resolve_ghost_anchor_filter_from_env` helper, 在 `from_exact_core` 调用前注入
- `src/tests/test_ghost_anchor_filter.py` 11 测试 全过 (filter=None / subset / 空集 / 出格 + env parser 6 个)
- `scripts/anchor_slicing_ram_poc.py` env-gated RSS curve 监控脚本
- 246 master regression test 全过, baseline 不破

**PoC 数据** (`.artifacts/anchor_slicing_poc/rss_curve_filter_0-0.csv`):

| 时刻 | filter=(0,0) | baseline (memory p1_24) |
|---|---|---|
| 1:00 | 12.43 GB | 8.87 GB |
| 2:00 | 16.98 GB | 10.76 GB |
| 3:00 | 18.61 GB | 30.01 GB ← 飙 |
| 5:00 | 23.36 GB peak | (撞 OOM) |
| 6:10 | exit 0 | crash |

**Peak: 23.36 GB. Delta: -6.65 GB / -22%**.

**判定 KILL**:
- 任务 #67 阈值 50% (RSS ≤ 15 GB / worker 才 -p 2 安全), 实测 -22%, 差 28%
- 23 × 2 + 8 host = 54 GB > 48 GB host, 仍不能 -p 2
- 23 × 4 = 92 GB > 48 GB, 远远不能 -p 4
- 跟 GPT v3 第二次 transcript 自己说的 caveat 完全吻合: "RAM 实际减多少没人本机量过 — **大头若 facility 部分则只减 20-40%**"
- 落在 20-40% 区间下沿 → ghost overlay 确认是配角, 大头是 mandatory facility CP-SAT model + propagation table

**软方向再死一个 (跟 [[p1-24-oom-blocked]]) 累加列**:
- CP-SAT 参数 sweep — 不影响 model 大小 (验过)
- Cuts persistence — cuts 没产撞墙 (验过)
- jemalloc / THP / cache trio — alloc 速度优化, 不减总量 (验过)
- A 方案 anchor slicing — ghost 是配角, -22% 不够 (今天验过)
- max_memory_in_mb env — OR-Tools 不限 RSS (验过)

**留 land 不 revert 因为**:
- anchor_filter hook 是 build-time tool, PROJECT_LOCK 兼容 (filter=None 全保留旧 behavior)
- 测试稳, 没破 baseline
- 给未来留备用 (e.g. 调试单 candidate 的 boundary precheck behavior; 或后续做 disjunctive decomp 时复用 plumbing)

**任务 #67 真路径剩什么 (跟 [[p1-24-oom-blocked]] 累加)**:
- 算法层面更深: 改 master representation / 拆 LBBD 跨更细 / 用 LP relaxation 代 CP-SAT master
- 这些都是周量级大改, 不在当前 session scope
- GPT v3 第三次包 (等回复) 可能还能加新方案, 但 ghost-anchor slicing 这条**不必再试更宽 filter 验证** — 配角就是配角
- 硬件方向已被用户排除 ([[p1-24-oom-blocked]])

**memory 链**:
- [[p1-24-oom-blocked]] 主上下文, 所有 RAM 实测数据
- [[v4-followup-landed-next-main-line]] 主线 next step
- [[research-roi-metric]] PoC 验证比 reconstruct GPT 4500 行 patch 更优 (今天 30 min PoC 出结论, GPT v3 几小时的 reconstruct 会浪费)
