---
name: benders-loop-mypy-followup
description: "benders_loop.py 还有 8 个历史 mypy 类型错, 暂不进 preflight gate; G2 留个跟踪"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

GPT v4 follow-up G2 把 mypy 进了 preflight, 但 scope 严格限定 `cut_manager.py` + `power_placement_subproblem.py` 两个 cut lifecycle 直接相关的核心 schema 文件 (已干净).

`src/search/benders_loop.py` (5400 行) 因历史类型错多, 单独修是大工程, 没进 gate. 现存 mypy 错 (2026-05-14 实测):

```
benders_loop.py:489   run_benders_for_ghost_rect.last_run_metadata = ...  [attr-defined]
                      — 函数对象动态加属性, mypy 不识. cast(Any, fn) 或 setattr
benders_loop.py:1868  proof_summary 重新声明类型 [no-redef]
benders_loop.py:2938  object 不支持 [index] — 某 nested dict 推断成 object
benders_loop.py:2986  int(object) [call-overload] — 同上, 推断断
benders_loop.py:2987  同 2986
benders_loop.py:3786  int(Any|None) — None 没 check
benders_loop.py:3962  powered_templates 缺 type annotation
benders_loop.py:5415  同 489 (closing)
```

**Why 不修**: 
1. 这些是 benders_loop 历史代码遗留, GPT v4 finding 没直接指到它们.
2. 全修需要把 build_stats / proof_summary / metadata 这些 deep-nested Mapping/Dict 类型完整描述, 工作量 1-2 天.
3. 我新加的 `_resolve_condition_lits_from_condition_set` helper 不在错误列表 — 说明 lifecycle-relevant 新代码已合规.

**How to apply**:

- 任何 benders_loop 大改 / refactor 时, 顺手把对应区域的 mypy 修了, 不要一次性修完.
- 若以后要把 benders_loop 进 mypy gate, 先把 build_stats / proof_summary 抽出 TypedDict, 让类型推断不再 fallback object.
- 修 489 / 5415 那俩 last_run_metadata 最优解: 把 module-level `_LAST_RUN_METADATA = {}` + accessor, 而不是给函数对象挂属性 (Python 允许但 mypy 不推荐).

跟 [[proof-object-lifecycle]] 关联: typed schema 是 lifecycle 闭环的辅助轮 — 强类型能逼着 schema 字段同步 resolver. benders_loop 现状是 lifecycle 检查靠测试 + preflight gate 不靠类型.
