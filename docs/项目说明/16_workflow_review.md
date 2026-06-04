# 16 — 审查策略 (Gemini per-commit + GPT pro 大节点 + 数学层验证 workflow)

Phase 1.1 经验: Gemini 11 round Day 15/16a/16b 堆到 round 14 才 cross-check, 找出 3 致命 bug + 2 schema 漏 — 单 spec single-step cross-check 防 cascade ([[gemini-review-algorithm-math]]). GPT pro 11 round v1-v6 audit catch 4 critical blocker (F1 demand P(g)⊆R / F2 partition / F3 cert↔literal / F4 commodity) Gemini 全 miss — 那是 adversarial soundness 层 ([[adversarial-soundness-audit]]). 两层分工互补, Phase 1.2 不可少.

### 22.1 Gemini per-commit cross-check (fast, narrow, schema layer)

**触发条件 (每 commit 必经)**
- 任何 src/cuts/ 改动 commit 后立刻调 ([[gemini-review-algorithm-math]] 用户原话: "先 check, 以后都是先 check 再继续", 不堆)
- 纯 implementation 不算 (refactor / rename / IO / docstring 改); 数学/算法/spec/schema 层必跑
- helper 拆 / radon D 级降 (§10.6) 算 refactor 但若动 validator 路径仍跑

**模式 (per [[gemini-prompt-audit-mode]])**
- audit 模式, 不是 GO 章 ritual: 验 spec ↔ src ↔ data gap, push find problem
- prompt 含 real data path (`data/preprocessed/candidate_placements.json` 等), 不只 sample
- armor: 强制 3 死法 + 反 vague hyperbole + 不重写 prompt 别调
- "GO" 不是 verdict 目标; "specific finding + reproducer" 才是

**频率 / 工时**
- 单 commit ~5-10 min round-trip (free-tier API key, [[gemini-math-consultant]])
- Gemini round number 在 archive 文件名连号 (Phase 1.1 时止于 r35; Phase 1.2 后另有 `p1_2b_f*_gemini_round*` 等命名, 以 `docs/research/` 实际归档为准, 不再单一连号)
- archive 立即 cp 进 `docs/research/.../cross_check/gemini_round_NN_*.md` ([[archive-research-transcripts]])

**Phase 1.2 加严 (R34 round 加严)**
- 每 commit 立刻 cross-check, **不堆**. 不准 "5 commit 后一起跑" — Day 15 累积 cascade 教训
- finding 必先 reproduce (script / grep) 才 archive 进 cross_check/, 不准 archive 假 finding ([[audit-verify-before-archive]])

### 22.2 GPT pro 大节点 batch audit (deep, broad, adversarial layer)

**触发条件 (大节点 boundary)**
- Phase 1.1 闭环 ✓ (v1-v6 已经跑过 11 round)
- Phase 1.2 入门 7 项 (§10) close — next trigger
- Phase 1.2 5 family 全 land (P1.2B-F5..F9) — next next trigger
- Phase 1.3 propagator land + 24h shadow trial — next³
- Phase 1.5+ production integration — final pre-168h

**模式 (per [[big-milestone-gpt-pro-review]] + [[review-pkg-no-prompt-inside]])**
- 打包 7z + zip 壳 + ship 7za binary (per `[[review-pkg-7z-strategy]]`, ~5-7 MB 全项目)
- prompt 不放包里, 通过 chat message 单独给 ([[review-pkg-no-prompt-inside]])
- armor 三段式 ([[gpt-review-prompt-armor]]): 真瓶颈 + 死路黑名单/白名单 + 不可达必须形式化证明 (不准 "I believe / intuition")
- 包 standalone — 不引用历史 GPT verdict ("跟 v3/v4 不一样" 这类不写, 详 [[review-package-for-new-window]])

**adversarial soundness check 清单 (主战场, GPT pro 主要 catch 这层)**

按 [[adversarial-soundness-audit]] 5 验:
1. **cert 内 sound**: cert 本身字段一致 (region cells ⊆ free / partition A∪B==free / commodity_id ∈ registry / src/sink_component bitset 真 BFS)
2. **cert ↔ literals 绑定**: F3 cert blocking_pose_id == literal multiset; F5 cert ↔ literal pattern 严等
3. **cert ↔ 真数据**: cert region 跟 canonical_rules.json 的 placement_rule_for_group 同源; cert commodity 跟 generic_io_requirements.json 真存在
4. **cert ↔ state**: cert 跟 BState `pose_domain` / `cell_owner` / `commodity_demands` 一致, 不是 oracle 凭空造
5. **cert ↔ 不变量**: cert 跟 PROJECT_LOCK §3A invariant 一致 (GHOST_AGNOSTIC sentinel / family-mode XOR / source_digest)

GPT pro 主要 catch (3+4+5) — Gemini 倾向 catch (1+2) schema 层. 实施 family validator 必主动想: "假 cert 能不能 pass?" Step A-O 教训.

**频率 / 工时**
- 1 大节点 ~ 1-2 round (打包 + 等 GPT pro verdict + close P0). Phase 1.1 用了 11 round 是因为反复 NOT GO + 我修 + 再打包. 正常 1-3 round
- 单 round 工时: 打包 5 min + 等 GPT 几 min + close finding ~30 min - 数小时 / P0
- archive: `docs/research/.../external_review/gpt_pro_phase{N}_v{V}_audit_*.md`

### 22.3 audit verdict criteria — GO / NOT GO

我们对 reviewer 的 verdict 怎么定义:

**GO 准则 (大节点过 audit)**
- 0 P0 (critical, soundness 破坏 / 生产 crash)
- ≤ 3 P1 (high, soundness 减弱 / 非生产路径 bug), 各有 mitigation 计划
- P2/P3 (medium/low, cosmetic / cleanliness / nice-to-have) 不卡 GO, 进 followup queue (#239)
- **⚠️ (2026-06-04) 大节点正式 close（如 spike close）门禁已提高 = 连续 ≥3 次独立审查零问题**——不是单次 batch 0-P0 即过；任一轮再现 finding 则连续计数**重置**。上面的单-round GO 准则用于判"是否推进下一步"，**正式 close** 用 ≥3 连续清零。见 memory big-milestone-gpt-pro-review。

**NOT GO 准则 (不推下一 phase)**
- ≥ 1 P0 → 必 close (Step A-O 模式) 才下一 round
- > 3 P1 → 排序 close top-3, 余进 followup
- 同 round 重复 catch 同 finding → spec drift, 必同步 spec/src/test 三层

**P 分级判定 (跟 GPT pro / Gemini 沟通时怎么定)**
- P0: validator 可被假 cert 骗过 (Step A-O 全部 P0 都属此); 生产 crash; data corruption; soundness 数学根据被否定
- P1: validator 不验某 sub-invariant 但当前数据不触 (Phase 1.2 加 fixture 触发); 静态工具 strict 不通过 (mypy/radon 严警); spec 跟 src drift 不致 soundness 破
- P2: dead code / 注释错 / docstring 旧; lint 非 fail
- P3: cosmetic / 风格

### 22.4 review 输入 / 输出 (各 reviewer 各自要看的)

**Gemini per-commit 输入**
- diff (commit SHA) + 改动 file 全文 + 相关 spec section (e.g. cut_family_specs/F1.md)
- 真数据 path (e.g. data/preprocessed/candidate_placements.json) — 让 Gemini 跑 reproduce
- 不放: full project, 历史 GPT verdict, 多 commit 累积 diff

**GPT pro batch 输入**
- 全项目 zip (v8 模式, 7z 壳 + ship 7za)
- 真数据 production 全集 (53 MB)
- audit archive 累积 (cross_check/ + external_review/) — 给 reviewer context 知道之前怎么修
- spec 完整 (cut_lifecycle_v2 / state_machine_v2 / cut_family_specs/)
- 不放: plan doc (主动性引导, per [[review-pkg-no-prompt-inside]]); prompt; verdict claim / Close 列表

**输出 archive 政策 ([[archive-research-transcripts]] + [[audit-verify-before-archive]])**
- Gemini response 立即 cp 进 `cross_check/gemini_round_NN_<topic>.md`
- GPT pro response 立即 cp 进 `external_review/gpt_pro_phase{N}_v{V}_audit_round{R}_{VERDICT}.md`
- 每 finding 必 reproduce verify (~5-15 min, cheap) 才算数; reproduce fail 标记 "unverified" 不计入 verdict P 列表
- archive 进 git, 不准只本地 — review pkg 给下个 reviewer 时也带上 archive

### 22.5 Gemini vs GPT pro 分工 summary

| 层 | Gemini | GPT pro |
|---|---|---|
| 频率 | per-commit (高频, 1-2/day) | 大节点 (低频, 1-2 round/phase) |
| 输入 size | diff + 单 spec section + 真数据 path | 全项目 zip |
| 主战场 | schema ↔ src ↔ data gap | adversarial soundness (假 cert 能 pass 吗) |
| 强项 | 自然口吻写作 + 快速 schema check ([[gemini-better-at-natural-tone]]) | deep cross-file consistency + paradigm check |
| 弱项 | 不会 push adversarial 反例构造 ([[gemini-prompt-audit-mode]] armor 补) | 慢, 不能 per-commit |
| 工时 | ~5-10 min/round | ~打包 5 min + GPT 等 + close 30 min-小时 |
| Phase 1.2 政策 | 加严: 每 commit 立刻, 不堆 | 大节点 trigger, 5 family land / Phase 完 |

---


## 6. 数学层验证 workflow

项目数学层验证 4 层. 各层独立 verify, 全 pass 才算 sound. 详 plan §22 (audit strategy).

### 6.1 Gemini per-commit cross-check (schema layer)

**频率**: 每 commit (cut framework src 改动) 立刻调.

**主战场**: schema ↔ src ↔ data gap. 验:
- spec 写 X 但 src 实施 Y → flag
- src 用 field A 但 BState schema 没有 A → flag
- real data path 数据 contradict cert claim → flag

**强项**: 自然口吻写作 + 快速 schema check ([[gemini-better-at-natural-tone]])

**弱项**: 不会 push adversarial 反例构造. 需 audit armor 强制 ([[gemini-prompt-audit-mode]])

**Phase 1.2 政策加严**: 每 commit 立刻 cross-check, 不堆 ([[gemini-review-algorithm-math]] R34 加严). 纯 implementation (refactor / rename) 不算数学层, 不必跑.

**输出**: `docs/research/.../cross_check/gemini_round_NN_<topic>.md` archive

### 6.2 GPT pro batch audit (adversarial soundness)

**频率**: 大节点 boundary — Phase 1.1 闭环 ✓ / Phase 1.2 入门 close / Phase 1.2 5 family land / Phase 1.3 propagator land / Phase 1.5+ pre-168h.

**主战场**: adversarial soundness §2.6 5 verification 层. 主 catch (3+4+5):
- cert ↔ 真数据 (oracle 凭空造的 cert)
- cert ↔ state (oracle 错绑 state field)
- cert ↔ 不变量 (oracle 违反 LOCK §3A invariant)

**强项**: deep cross-file consistency + paradigm check

**弱项**: 慢, 不能 per-commit; 不引用历史 GPT verdict (新窗口零 memory, [[gpt-review-no-history]])

**审查 armor**: 三段式 prompt ([[gpt-review-prompt-armor]]):
- 真瓶颈讲清 (项目是 latency-bound 不是 bandwidth-bound, 等)
- 死路黑名单 / 可接受方向白名单 (27 lever 死路 + cut framework paradigm 白名单)
- 不可达必须形式化证明 (complexity reduction / proof system lower bound / resource inequality / cite literature, 不准 "I believe / intuition")

**包 strategy**: 全项目 7z + zip 壳 + ship 7za binary ([[review-pkg-7z-strategy]]). plan/roadmap 不放包内 ([[review-pkg-no-prompt-inside]]).

**输出**: `docs/research/.../external_review/gpt_pro_phase{N}_v{V}_audit_round{R}_{VERDICT}.md` archive

### 6.3 真数据 reproduce (cheap gate)

**频率**: 任何 paradigm propose 新方向, 实施前 ≤ 1h cheap gate. ([[paradigm-phase0-cheap-gate]])

**主战场**: paradigm 前提**是否真满足 instance**.

**典型死法 catch**:
- v8 anchor slicing (关注 build 没量 solve)
- v10 witness preflight (假定 blueprint 满 41 mandatory 但实际缺)
- L14 weighted occupancy (interior LP=1.000 永不可 cert)
- L15 set-packing prover (攻错层)

**实施**:
- 写 Phase 0 PoC (~几百 LOC)
- 跑 production data subset (10-50 instance)
- 量 metric (m1-m10 各 paradigm 不同, 但通常含 sound 性 + cut 强度 + RAM/wall)
- pass 才进 Phase 1 实施 (full LOC)

**输出**: `docs/research/<paradigm_name>_<date>/phase0_*.md` archive

### 6.4 形式化 proof 跟工程 verify 的边界

**当前项目政策**: 数学 sound 用工程 verify (validator 重算 cert), 不用形式化 proof system (Coq / Lean / Isabelle).

**为啥**:
- 形式化 proof 投资 ≥ 数月 / family (Coq 项目典型 size)
- 项目 9 family 形式化需 ≥ 数年 — 不在 Phase 1-2 scope
- 工程 verify (validator 重算 + adversarial audit + telemetry 反推) 在项目 budget 内 sound 度足够

**何时 reconsider**:
- 项目交付后维护期 (Phase 3+) 若 data schema 大改, 形式化 proof 防 regression
- paradigm 投入 (defer Phase 2+) 时 formal proof 给最强 evidence

**当前 Q14 P3 defer**.

### 6.5 跨层一致性

3 层 verify 各自独立, 但**结果必一致**:
- Gemini per-commit pass + GPT pro NOT GO → 必查 Gemini 漏 audit layer (通常是 adversarial soundness 层 Gemini miss)
- 真数据 reproduce fail + Gemini/GPT pass → 必查 audit prompt 是否提供真数据 path
- GPT pro 多 round verdict 不一致 ([[external-review-reproducibility]]) → finding 必 reproduce verify, 不照搬

---

