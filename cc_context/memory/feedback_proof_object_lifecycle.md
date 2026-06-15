---
name: proof-object-lifecycle
index_summary: "generate→…→replay→regression; schema landed ≠ runtime correct."
description: "任何 persisted exact-safe proof object 必须 6 步生命周期闭环, 缺一不可 (GPT v4 audit lesson)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

任何 persisted exact-safe proof object (BendersCut.condition_set, BendersCut.metadata, 其他要进 campaign checkpoint 的字段) 都必须有完整 6 步闭环, 缺一不可:

```
generate -> serialize -> deserialize -> validate -> resolve runtime literals -> replay -> behavioral regression test
```

**Why:** GPT v3 review 抓到 "接口形状诱导 over-cut", v4 review 抓到的不是接口形状, 是**生命周期断裂** — v4 commit `7ffb1f4` 给 `BendersCut` 加了 `condition_set` 字段, master.add_benders_cut 加了 `condition_lits` 参数, **runtime path 修对了**, 但 `run_benders_for_ghost_rect` 的 replay 路径只重传 `cut.conflict_set` 不传 `condition_set` → conditioned cut 重放成 unconditional → 过切. 

readiness gate / wrapper / PROJECT_LOCK forbidden line 当时都加了, 但这些是"门口护栏", 不是"代码自洽". gate 一被 bypass / preloaded_exact_safe_cuts 一被外部注入 / feature 一被未来重开, exactness 立刻破洞.

GPT v4 dynamic probe (固化在 `test_benders_cut_replay_condition_lifecycle.py`):
- 直接 add_benders_cut(conflict, condition_lits=[u_var]) → protobuf constraint enforcement literal = 1 ✓
- 走 replay 路径 add_benders_cut(cut.conflict_set) → enforcement literal = 0 ✗ (条件丢了)

**How to apply:**

1. 给 BendersCut / persisted artifact 加新字段前, 先在 PR 描述里列 6 步谁负责. 任一步未实现 = 该字段不能进 certified mode (即使有 gate 兜底).
2. validate 步不能省: 反序列化后必须 cross-check 跟 master 当前状态一致 (例如 ghost anchor coord 和 rect_idx 对得上). 不一致 → certified mode fail-closed skip, 不退化成宽松形式.
3. resolve 步必须有显式的 resolver 函数, 不能在 caller 里 inline 拼. unknown key 类型必须 ok=False, 不能默默忽略.
4. regression test 必须是**行为式断言**, 不只是 "API 直接调返回 True". 至少要构造 ghost A → persist → ghost B replay 看会不会 over-prune.
5. 跟 keep-review-process-light(已归档) 配合: lifecycle test 应该轻 (0.1s 量级), 进 CORE_TEST_FILES / preflight gate. 一个 lifecycle test 比 100 个 direct API happy path 更值钱.
6. 跟 [[verify-solver-param-claims]] 同源: schema landed ≠ runtime correct. "看起来对" 不算 verify.

**触发场景**: 任何 `src/models/cut_manager.py`, `src/search/benders_loop.py`, `src/search/exact_campaign.py` 里的 persistable field 改动. 改 schema 必须同时改 resolver + replay + test.

**Why this is harder than it looks (Anthropic "Teaching Claude Why" 的 generation 内在倾向问题)**:

我自己写 schema 时 default 假设是 "schema landed → 后续都自然用上". 这个默认假设在 stateful pipeline 里是错的 — pipeline 有多条 reentry 路径 (live infeasible / replay / preloaded inject), 每条都要单独 wire. 写完 generate path 后必须主动问 "这个 object 会不会被 read 回来? 谁 read? read 时谁 resolve 字段?". 不问 = lazy 路径 = bug 潜伏.

## 链 (补连 2026-06-02 连通审计 whcb890zi)
- [[verification-independent-backstop]] — 6 步闭环=独立行为验证, schema landed≠runtime correct 同 anti-self-trust
