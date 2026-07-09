---
id: ortools-915-proto-wrapper-pitfalls
kind: pitfall
title: ortools 9.15 包装 proto 三连坑：oneof 脏读 / repeated append 损坏 / clear 整字段才安全
summary: 直接访问 CpModel proto 里未设置的 oneof 子消息（如 constraint.no_overlap_2d）会读到脏内存——约束类型误判且不报错；可靠判别必须走 has_*() 方法（has_no_overlap_2d() 等）。对包装 proto 的 repeated 字段做 append/extend 会损坏 solver 内部状态（MODEL_INVALID "Interval 0 does not refer..."）。清空约束的合法操作是 clear_no_overlap_2d() 这类整字段清空（= 合法 no-op 约束）。2026-07-09 修复 C（no_overlap dedup）时全部实测踩过：第一版用字段访问判别差点误清 interval 约束，被语义测试拦下后改 has_*()。
scope:
  domains:
    - ortools-api
    - master-model
    - measurement-harness
  paths:
    - src/models/exact_coordinate_master.py
    - src/tests/test_coordinate_no_overlap_dedup.py
  symbols:
    - has_no_overlap_2d
    - clear_no_overlap_2d
    - _dedup_subsumed_core_no_overlap
status: active
priority: P1
error_regex:
  - "MODEL_INVALID[\\s\\S]{0,200}does not refer"
triggers:
  intents:
    - proto-inspection
    - constraint-surgery
  keywords:
    - no_overlap_2d
    - proto
    - WhichOneof
    - MODEL_INVALID
    - clear_no_overlap
  negative_keywords: []
  paths:
    - src/models/exact_coordinate_master.py
  symbols:
    - has_no_overlap_2d
    - clear_no_overlap_2d
  error_regex:
    - "MODEL_INVALID"
    - "does not refer to a supported interval"
  examples:
    - 写探针数模型里的 no_overlap_2d 约束该怎么判别类型
    - 为什么 append 进 proto repeated 字段后 solver 报 MODEL_INVALID
activation:
  layer_hint: L1
  reason: proto 级模型手术/探针是低频动作，关键词召回（no_overlap_2d/proto/MODEL_INVALID）足够，不需常驻。
provenance:
  op: record
  reason: 2026-07-09 修复 C（no_overlap dedup）期间三坑全部实测踩过，误清 interval 约束被语义测试拦下后确立 has_*() 纪律。
  evidence:
    - src/tests/test_coordinate_no_overlap_dedup.py::_live_no_overlap_count（has_no_overlap_2d 标准用法）
    - git show c3d64c4（dedup 实现，clear_no_overlap_2d 用法）
updated_at: "2026-07-09"
---

## 事实（2026-07-09 修复 C 期间实测）

1. **oneof 脏读**：ortools 9.15 的 Python 包装 proto 没有 `WhichOneof`；直接访问未设置的 oneof 子消息字段（`constraint.no_overlap_2d`、`constraint.interval` 等）**不抛错、返回脏内存**——用它判别约束类型会误判。第一版 dedup 因此差点清掉一个 interval 约束，被语义回归测试（MODEL_INVALID）当场拦下。
2. **可靠判别** = `constraint.has_no_overlap_2d()` 这类 `has_*()` 方法（proto 包装暴露了它们）。`test_coordinate_no_overlap_dedup.py::_live_no_overlap_count` 是标准用法。
3. **repeated 字段 append 损坏内部状态**：往包装 proto 的 repeated 字段直接 append/extend 会让 CP-SAT 报 `MODEL_INVALID "Interval 0 does not refer to a supported interval constraint"`。别用 proto 面做"加约束"。
4. **合法的删除**：`constraint.clear_no_overlap_2d()` 整字段清空后该约束成为合法 no-op（玩具验证过），生产 dedup（`_dedup_subsumed_core_no_overlap`）就用它。

## 第四坑：has_*() 反射在部分 proto 形态下直接段错误（2026-07-10 外审复现+本机坐实）

最小模型（2 个 IntVar + 2 个 interval + AddNoOverlap2D）上调 `constraint.has_no_overlap_2d()` **进程级段错误**（SIGSEGV，faulthandler 定位在调用行；`NewIntervalVar`/`NewFixedSizeIntervalVar` 形态都复现）。而完整 build 的生产模型上同一调用长期稳定（dedup 单测+全天生产实证）——触发条件未完全定界。**结论：证明语义热路径禁止依赖 proto 反射判型**。替代姿势 = 自己建约束时记下 `constraint.Index()`，之后按 index 定位（类型已知，直接读字段安全）；修复 C 的 dedup 已于 2026-07-10 按此重写（`_core_no_overlap_constraint_index` + 逐 interval 子集校验）。测量探针里仍可用 has_*()（如 `_live_no_overlap_count`），但要接受它可能在极简模型上炸——探针炸只损失一次测量，证明构建炸是生产事故。

## 适用面

任何 proto 级模型检查/手术：测量探针数约束、dedup 类修复、编码原型的 build 对照。批 0/批 1 的 C6/C1 工作都会反复碰。
