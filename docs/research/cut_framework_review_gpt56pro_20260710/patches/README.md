# 补丁顺序

基线：项目包 committed tree。

1. `0001-cuts-seal-integrity-at-irreversible-attach-boundary.patch`
   * 阻止 body/cert split-brain 到达 master。
   * 增加拒绝原因 telemetry 与恶意回归。
2. `0002-cuts-preserve-ghost-width-and-height-in-BState.patch`
   * 修复 `(width,height)` 到 `(x,y,x_span,y_span)` 的轴顺序。
   * 新增非方形 ghost 回归。
3. `0003-cuts-require-complete-artifact-scope-snapshots.patch`
   * schema v1 下要求 artifact scope 与 state 完整快照严格相等。
4. `0004-cuts-type-canonical-relabel-slot-counter.patch`
   * 仅补全 bare generic 注解，使 mypy strict 全绿。

建议把 0001 至 0003 当作通电前阻断性修复；0004 是低风险工程卫生。完整应用和测试日志见 `../evidence/patch_apply_and_test.txt`。
