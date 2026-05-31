---
name: gpt-v13-cut-language-thesis
description: "2026-05-21 GPT 三份独立答复共同 thesis: 换 cut 语言不是换 solver. 击中 cand C Phase 3/4 vulnerability — dual 仍停在 cell/facility 级, 真接 routing 时可能撞回 24 lever 同墙"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

2026-05-21 GPT (非 v12 review channel, 用户 ad-hoc 问) 三份独立答复共同 thesis: **换 cut 语言不是换 solver**.

## GPT 三份核心 thesis (high agreement across 3 runs, reproducibility OK)

主张:
- 现 master 只听得懂 "这个 pose 组合别再出现" (pose no-good)
- 新 master 应该听懂 "这类区域容量不够 / 这类端口暴露方式必死 / 这个割集过不去"
- **换 cut 语言不是换 solver**. 不要 abort CP-SAT, 不要重写通用 SAT/CP/MIP

反对的路径:
- 直接换 Choco / Gecode / MiniZinc / Z3 / clingo (换壳不解决 cut 表达力)
- 直接接 Gurobi/SCIP 作主脑 (黑盒搜索, lazy cut 仍弱)
- 把 routing 全量塞 master (重蹈 L23: 2.68M cstr / 32 GB)
- 从零写通用 SAT/CP/MIP solver (无底洞, 不对症)
- **把 column generation 当第一主线** (但实测已反驳, see "GPT 担心被 cand C 实测反驳" 段)

推荐 5 类强 cut (cand C 现在没有, Phase 3/4 必须接):
1. **Region capacity cut**: 区域最多放下 N, 当前要求 N+1 → 全 ban
2. **Separator / cutset cut**: 左 source 右 sink 中间缝容量不够 → 全 ban
3. **Port exposure cut**: 兼容方向端口供需不平衡 → 全 ban
4. **Component reachability cut**: 某类对象被切成不连通孤岛 → 全 ban
5. **Pattern no-good cut**: 局部 layout 形态 ban (跨 anchor 复用)
6. **Symmetry-lifted cut**: 一个 cut 自动复制到 orbit

推荐技术栈 (long term):
- Python orchestration + Rust/C++ bitset kernel
- Gurobi callback / SCIP plugin 做 branch-and-cut shell
- PySAT/CaDiCaL 做局部 SAT core
- VeriPB 做 pseudo-Boolean proof certificate
- CP-SAT 保留作 oracle/verifier
- Hexaly/local search 只作 hint generator 不作 certified path

推荐自研模块:
1. PoseStore (bitset-first 数据结构)
2. SearchState (trail stack + undo)
3. OracleRunner (统一 binding/routing/power/connectivity 检查, 返 minimal_explanation + proposed_cut + proof_payload)
4. CutFactory (validity checker 必须, 无 checker 不进 certified path)
5. ProofLog (每条 cut 独立 replay, schema-first 不 retrofit)

## GPT 担心被 cand C 实测反驳

GPT 把 column generation 排"最低优先级", 担心:
- column = single pose → 等价当前 master
- column = whole layout → pricing = 原问题

但 cand C Phase 1 实测反驳:
| 实测 | 反驳 |
|---|---|
| m12 avg fac/col 6.05-6.57 跨 ramp 稳定 | 中间粒度真存在, 不退化 single 也不退化 whole |
| m10 integer validator True 全 ramp | sound 性 strict + equiv 全 cover |
| m11 branching nodes 11/33/53 | branch tree 小, master basis 健康 |
| m9 proxy dual 0% 全 ramp | boundary 不紧 |

GPT 是 a priori 担心, 我们是 a posteriori 实证. Cand C Phase 0/1 不该 abort.

## GPT 真正击中的 cand C 弱点

Cand C 当前 dual 仍在 **cell + facility 级别**:
- π_iid = mandatory facility coverage dual
- cell_penalty = grid cell capacity dual

跟 GPT 提的 5 类 cut **完全不同维度**.

Phase 3/4 接真 routing 时, 如果 cut 仍是 cell/facility 级 → routing 失败翻译回 master 仍只能 ban pose 组合 → cand C pattern variable basis 优势被 cut 弱化抵消, 撞回 24 lever 同墙.

**这是 GPT 真正击中的 vulnerability — cand C 现在没有 cut language 升级的设计**.

## 两条路线正交 stack

| 路线 | 改什么 | 当前 |
|---|---|---|
| cand C | master 看的对象 (facility → pattern) | ✅ Phase 0/1 GO, Phase 2 跑中 |
| GPT v13 | cut 反馈的语言 (cell/pose dual → region/cutset/port-budget) | ❌ 未实施 |

**正交不冲突可 stack**: cand C 让 master 看 pattern, GPT 让 master 听 region capacity cut.

## 行动

- **不 abort cand C Phase 2** (跑中, 已 1 hr+)
- **Phase 3/4 设计文档**纳入 GPT 5 类 cut 框架
- **Phase 4 必做**: pricing dual 升级到 region/cutset 级别 (不只 cell/facility)
- **bitset-first 数据结构**作 Phase 4 实施基础
- **proof object lifecycle** schema-first, 不 retrofit

## Refs

- 用户 2026-05-21 ad-hoc GPT 询问 (非 v12 review channel, 3 份独立答复)
- Cand C Phase 1 4-ramp GO [[cand-c-phase1-go]]
- Cand C Phase 0 8/8 GO [[cand-c-column-generation-phase0-go]]
- v12 review 历史 [[v7-review-package-landed]] / [[v8-anchor-slicing-dead]] / [[v10-witness-preflight-dead]]
