# binding_canonical_semantics_v1 —— sidecar 语义规范（源码逐行核对版）

> 设计稿 v2 §3.3 要求的语义来源三层声明。每条标注：来源层（F=冻结数据可复算 /
> H=生产源码硬编码 TCB / P=pending 前端）+ 源码锚点（2026-07-05 main HEAD）。
> emitter/witness checker 实现必须逐条对照本文件；本文件修订 = 语义变更，须重审。

## 1. strict JSON（F；`src/io/strict_json.py:17-67` 逐行核对）

- 拒绝重复 object key（`ValueError: duplicate JSON key`）；
- 拒绝 NaN/Infinity/-Infinity 常量（parse_constant 一律 raise）；
- float token 解析后必须 `math.isfinite`，否则 raise（如 `1e400`）；
- 文件读取 UTF-8。
- sidecar 独立实现 = 同样的 `json.loads` 三 hook（stdlib json 属 Python 运行时，
  不算生产代码共享）。

## 2. operation profile（F+P；`operation_profiles.py:21-119` + `preprocess_context.py:32-44,71-76,803-889` 逐行核对）

- recipe 型 operation：`input_rate(c) = inputs[c] / ticks_per_cycle`（Fraction 精确；
  `output_rate` 同构）；`ticks_per_cycle` strict 正整数（bool 拒绝）；recipe 必须
  至少一个 output；inputs/outputs 金额经 `_to_fraction`。
- utility 型 operation：无 rates；`generic_input_slots`/`generic_output_slots`
  strict 非负整数（bool 拒绝）。
- **`_rate_to_slots`（核心上取整）**：rate ≤ 0 → 0；capacity ≤ 0 → raise；
  否则 `required = rate/capacity`（Fraction），slots =
  `(num + den - 1) // den`（精确 ceil，无浮点）。
- `_to_exact_fraction`：Fraction 原样；bool → TypeError；int → Fraction(v,1)；
  float → 有限性检查后 `Fraction(str(v))`（**注意：经 str 往返，不是二进制精确**）；
  str → Fraction(str)；其他 TypeError。
- `supports_exact_pose_level_binding(op)` = profile 的两个 generic slot 字段全零
  （`port_binding.py:31-33`）；非零时枚举函数 raise ValueError。
- **P（pending 前端）**：recipes/belt_capacity_per_tick/utility_operations 从
  canonical_rules.json + preprocess_plan.json 的完整解析
  （`build_preprocess_context_from_rules_and_plan`，831 行模块）——真实样本前端
  实现时逐字段规格化补进本文件；合成样本直接提供已推导的 slot counts，不经此层。

## 3. 域枚举（F；`port_binding.py:40-205` 逐行核对）

- port cells 规范化：{x:int, y:int, dir:str}；**按 (x, y, dir) 排序**；
- 每侧：required = profile 槽数表中 count>0 的 (commodity, count) 序列
  （**保持 profile dict 迭代序**——生产 `slot_counts.items()` 未排序，但
  profile 构造时 inputs/outputs 已按 commodity 排序，故实际 = 字典序）；
- 总需求 > cells 数 → **raise ValueError**（不是空域）；required 为空 → 单一空
  pattern `[()]`；
- 枚举 = 按 required 序做 backtrack：每 commodity 从剩余 cell index 中取
  `combinations(remaining, count)`（index 升序组合），choose 后 pattern 按
  cell index 排序输出 (idx, commodity) 元组；
- 两侧笛卡尔积 `product(input_patterns, output_patterns)`；
- **推论（v2 §2.4）**：域永非空（raise 或 ≥1 pattern）。

## 4. PortBindingModel 语义（F+H；`binding_subproblem.py` 逐行核对）

### 4.1 输入校验序（§2.2 全文有效，此处只记锚点）
- generic I/O 规范化+角色校验+完备性：`:305-435`；
- wireless K strict 非负 int：`:78-94`；
- pose_optional 合成（含 `::` 反推）：`:583-613`；ghost_pick marker：`:60,66-67`；
- metadata 一致性五类：`:650-759`；INVALID_INPUT 短路：`:1273-1288`；
- build 期 raise：`_resolve_pose` 越界 `:977-983`、`sol["facility_type"]`/
  `int(sol["pose_idx"])` KeyError/TypeError `:995-996`。

### 4.2 变量与约束
- binding 域组：`:985-1045`（|域|=1 fixed 无变量；|域|>1 ExactlyOne）；
- 域空 `0==1`：`:782-783`（Phase 1 纯模型不可达，见 v2 §2.4）；
- generic output 槽：`:1047-1086`（**H：provider 集合 = {boundary_io,
  protocol_core}**）；每 output_port_cell 一槽；commodity 集 = sorted(required
  outputs) + `__unused__`；ExactlyOne；
- generic input 槽：`:1095-1132`（**H：receiver 集合 = {wireless_sink}**）；
  K 个虚拟槽；同上 ExactlyOne；
- 计数：required>0 → `sum == required`；required==0 → 逐变量 `var == 0`
  （**不发 sum 行**）：`:1134-1158`；
- nogood（Phase 1 外）：materialized literals only，空集不加：`:1447-1463`。

### 4.3 硬编码 TCB 清单（H——sidecar 手抄，Phase 1 防不了，报告须声明）
- `POSE_OPTIONAL_OPERATION_BY_TEMPLATE = {protocol_storage_box: wireless_sink,
  power_pole: power_supply}`（`:56-59`）；
- `NON_FACILITY_PLACEMENT_MARKER_IDS = {ghost_pick}`（`:60`）；
- generic provider 集合 {boundary_io, protocol_core}（`:1058`）；
- generic receiver 集合 {wireless_sink}（`:1106`）；
- `supports_exact_pose_level_binding` 的 gate 定义（`port_binding.py:31-33`）。

## 5. OPB/工具链硬规格（F；实验+源码坐实，`toolchain_notes.md`）

- 扩展头 `* #variable= N #constraint= M #equal= K intsize= 0`；K=等式行数精确；
- 约束行终止 ` ;`；系数带显式符号；变量 `x1..xN`；
- RoundingSat UNSAT 退出码 1（禁 check=True）；veripb 失败退出码 0
  （禁退出码判定）；判定=结论行 anchored 唯一匹配。
