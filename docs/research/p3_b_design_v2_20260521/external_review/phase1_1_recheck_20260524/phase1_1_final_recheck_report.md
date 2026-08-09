# Phase 1.1 最终复查与补强报告（2026-05-24）

## 结论

**Phase 1.1 可以正式通过，进入 Phase 1.2。**

本轮是在 v10 / R3 final delivery 之后做的“再挑刺”复查。原有 1.1 主 gate 已经通过；本次又补上了一些更细的输入边界和文档口径问题。修完后，cut framework 的普通模式和 `python -O` 模式都稳定为 **188 pass**，静态工具全绿，exit criteria 是 **0 FAIL**。

## 这次重点查了什么

1. `src/cuts/lifecycle.py`：Cut 对象创建、序列化/反序列化、base64、bitset、scope/cert schema。
2. F1-F4 validator/evaluator：F1 `region_capacity`、F2 `cutset`、F3 `port_exposure`、F4 `component_reach`。
3. `python -O` 防线：确认没有靠 `assert` 才能守住 soundness。
4. 文档/门禁口径：README、当前状态、GO 标准、测试标准是否还停在旧的 181/178 或旧路径。
5. 工具门禁：pytest、ruff、mypy、vulture、bandit、radon、exit criteria。

## 查出的具体问题与修复

### 1. base64 解析太宽松

Python 默认 `base64.b64decode()` 较宽松，某些混入垃圾字符的 payload 可能被“忽略后照样解码”。这对 cut JSON 这种审计产物不合适。

修复：
- 新增 `_strict_b64decode(..., validate=True)`。
- `geometric_payload`、`cert.cert_payload_b64`、region bitset 解码全部走严格 base64。
- 新增回归：非法 base64 必须被拒绝。

### 2. region bitset 只看能不能解出 cells，不够严

旧逻辑对 bitset 长度/网格外高位没有卡死。70×70 grid 需要 4900 bit，最后一个 byte 里有多余 bit；这些多余 bit 不能被置 1。

修复：
- 校验 bitset byte 长度必须等于 `(70*70 + 7)//8`。
- 校验 grid 外多余 bit 必须全 0。
- 新增回归：高位置 1 直接拒绝。

### 3. Cut runtime schema 仍有小缝

`Cut.scope` / `Cut.cert` 之前主要检查“有无”，现在进一步要求必须是真 `CutScope` / `OracleCert` 对象；同时把 family、payload schema version、iter_index、active assumptions 等字段补成 fail-closed。

修复：
- `Cut.__post_init__` 拆 helper，避免一个大函数里混太多规则。
- `scope` / `cert` 类型强制。
- `family` 必须是 str 且在 9-family 表中。
- `CutScope`、`OracleCert`、literal、metadata、status 字段都补 schema 检查。
- Radon 从旧的高复杂度风险降回 average A / no D。

### 4. `bool` 被 Python 当成 `int` 的坑

Python 里 `bool` 是 `int` 的子类，所以 `isinstance(True, int)` 会返回 true。如果 validator 只用普通 int 检查，`True` 可能偷混成 `1`。

修复：
- F1/F2/F3/F4 中所有关键数字字段改成 strict int：必须是 `int` 且不能是 `bool`。
- 字符串数字例如 `"3"` 不再自动转 int。
- 覆盖字段包括 `cap_R`、`demand_R`、`gap`、`cells_per_pose`、`cut_size`、`commodity_demand`、blocking slot、cell 坐标等。
- 新增 4 个针对 bool/数字 schema 的回归测试。

### 5. malformed cert 的 evaluator 要保守失败

validator 已经会挡住坏 cert，但 evaluator 也不应该因为坏 payload 抛异常或走出奇怪结果。

修复：
- F2/F4 evaluator 遇到 malformed cert 直接返回 `False`。
- F4 commodity registry 的 src/sink cell 走严格 cell parser。

### 6. 文档口径有旧值和路径漂移

README 和项目说明里还有旧的 181 pass / root `external_review/` 口径。当前项目实际 archive 在 `docs/research/p3_b_design_v2_20260521/external_review/`。

修复：
- README 更新为 2026-05-24 recheck 版本。
- `docs/项目说明/06_current_status.md` 更新为 188 pass 和 0 FAIL。
- `docs/项目说明/12_go_criteria.md` 更新 gate 结果。
- `docs/项目说明/15_workflow_testing.md` 更新工具门禁口径。
- `docs/项目说明/04_design_invariants.md` 修掉“validator radon D by design”的旧说法，改为“不删 soundness binding，同时 helper 拆分保持 no D”。

## 新增回归测试

本次新增 7 个 cut framework 回归，测试数从 **181** 增到 **188**：

- lifecycle 非法 base64 拒绝
- lifecycle region bitset grid 外高位拒绝
- Cut scope 非 CutScope 对象拒绝
- F1 bool numeric 字段拒绝
- F2 bool commodity_demand 拒绝
- F3 bool blocking_slot 拒绝
- F4 commodity registry bool cell 坐标拒绝

## 验证结果

在项目根目录执行：

```bash
.venv/bin/python -m pytest src/tests/cuts/ -q
# 188 passed

.venv/bin/python -O -m pytest src/tests/cuts/ -q
# 188 passed, 1 warning（pytest 提醒 -O 下 assert 不执行，符合预期）

.venv/bin/python -m ruff check src/cuts src/tests/cuts scripts/vulture_cuts_whitelist.py
# All checks passed

.venv/bin/python -m mypy --strict --explicit-package-bases src/cuts
# Success: no issues found in 22 source files

.venv/bin/python -m vulture src/cuts src/tests/cuts scripts/vulture_cuts_whitelist.py --min-confidence 100
# pass

.venv/bin/python -m bandit -q -r src/cuts
# 0 issues

.venv/bin/python -m radon cc src/cuts -s -a
# Average complexity: A；无 D/E；最高 C(15)

.venv/bin/python scripts/b_design_v2_exit_criteria.py
# 3 PASS / 8 PENDING_PHASE_1 / 0 FAIL
```

`exit_criteria` 里的 8 个 PENDING 是 Phase 1.2/168h ramp 数据或后续 F7/F8/F9 等测试文件尚未生成，不是 Phase 1.1 阻塞项。

## 最终判断

- Phase 1.1 主闭环：通过。
- 1.1 代码门禁：通过。
- 1.1 文档口径：已对齐。
- 进入 1.2 的阻塞项：未发现。

建议下一步直接进入 **Phase 1.2B：F5 fallback 优先**，同时保留本轮新增 7 个回归，作为后续每次改 cut framework 的固定门禁。
