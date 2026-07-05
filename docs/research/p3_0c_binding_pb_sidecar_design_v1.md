# binding 子问题 PB 独立重建 + VeriPB sidecar——设计稿 v2

> 状态：v1 经双会话独立对抗审（均判 REJECT：方向保留、scope/输入契约/语义完整性/
> 验收强度四面重写），本版按两份审查意见融合修订。原件归档见审查目录 README。
> 归属：P3.0c 轴 B Phase 0+1（总路线图 `docs/项目说明/00_master_roadmap.md` §2b）。
> 上游依据：证书侧深研报告（`docs/research/p3_0_formal_reviews_20260705/p3_0_certside_route_research_gpt.md`）。
> 日期：2026-07-05。作者：数学面线程。

## 0. 一句话目标

对生产链宣布的 **binding INFEASIBLE** 判决，用一条**异构**旁路复验：从冻结工件
独立重建同一子问题的伪布尔（PB/OPB）编码 → 用原生产证明日志的求解器
（RoundingSat）重解 → 用独立检查器（VeriPB 3.0）复核其 UNSAT 证明 → 与生产
判决对账。**最危险的失败模式不是报 UNKNOWN，而是「证明了另一个模型 UNSAT、
被当成生产 binding INFEASIBLE 的证据」**（v1 两份外审的共同警告）——本版的
全部修订都在封这一条：scope 机器闭合（§1）、输入语义完整（§2）、语义来源
三层显式化（§3.3）、可对账样本记录（§3.4）、fail-closed 判定（§5）、
双向验收矩阵（§6）。

**三条已拍定约束**（owner 2026-07-05）：
1. **独立重建**——编码不从生产代码导出、不 import 生产 builder；
2. **纯旁路**——不写生产路径、不碰锁面、与 PR2 主线零文件交集；
3. **开发照 formal/ 模式**——仓库外开发，绿了经 worktree 落 main 独立目录。

## 1. 复验对象：机器可区分的 scope 分类（v2 重写）

### 1.1 生产侧 binding INFEASIBLE 的形态分类（不再按「首解/重解」二分）

v1 的「两种形态」不成立：至少存在四种「非纯 binding」路径能产出外观相似的
INFEASIBLE。进入 sidecar 前，每个样本必须携带 machine-readable
`binding_scope_class`，取值与判据：

- **`PURE_BINDING_INITIAL`**：`routing_context is None` ∧ 本次 build 的
  overload separation 关闭（`use_overload_separation=False` 或 env 未启用）∧
  `rejected_selection_count == 0` ∧ 本次 INFEASIBLE 来自初始 `solve()`
  （`solve_ordinal == 0`）。**Phase 1 唯一可复验对象。**
- **`ROUTING_AWARE_INITIAL`**：`EXACT_B1_ROUTING_AWARE_BINDING` 开启，
  routing_context 非 None——即使零 nogood，binding 域和 generic output 槽
  已被 routing-front 过滤（`binding_subproblem.py` 的 `_filter_pose_binding_domain`
  与 output-slot skip），empty-filtered domain 的 INFEASIBLE 外观像形态①但
  语义不是。→ `OUT_OF_SCOPE`。
- **`OVERLOAD_HEURISTIC_INITIAL`**：`EXACT_BINDING_USE_OVERLOAD_SEPARATION`
  在 build 时启用，模型带 hard overload nogood（可切合法解）。→ `OUT_OF_SCOPE`
  （除非样本明确指向 overload-off 的 fallback 重建模型）。
- **`REJECTED_SELECTIONS_ACCUMULATED`**：≥1 次 `add_nogood_cut(selection)`
  已进模型（binding-routing 交互命题）。→ `OUT_OF_SCOPE`（Phase 1.5+ 见 §3.2 NOGOOD 行）。
- **`INPUT_INVALID_OR_EXCEPTION`**：生产 build/solve 未形成合法 CP-SAT
  feasibility verdict（`INVALID_INPUT` 返回路径，或 build 期 raise）。
  → sidecar 不得编码为 UNSAT（见 §2 边界）。

**scope gate 铁律**：任何缺少 `binding_scope_class` 字段、字段无法由采集证据
复算、或字段与采集内容矛盾的样本，一律 `OUT_OF_SCOPE` / `INPUT_INVALID`，
不得 `CONFIRMED`。Phase 1 的 PASS 只表示「同一纯 binding 初始模型在
PB/VeriPB 链上 UNSAT」，不得向其他 scope class 外推。

### 1.2 与 I1 的关系（v2 修正：参照，不是相同对象）

I1（`independent_infeasibility_reverifier.py`）的 authority 对象是
**whole-layout INFEASIBLE cut 候选**（带 `proof_stage` / `binding_exhausted` /
`routing_exhausted` 标志）；其 Phase 1 策略是只接受一个充分条件——独立重建的
纯 binding 模型不可行（`build(use_overload_separation=False)`），routing
exhaustion 只有在该更强命题成立时才被保守确认。

**两点不得过度声称**（v1 实犯）：
1. I1 源码只强制关 overload；`binding_kwargs` 向 `PortBindingModel` 原样透传，
   「无 routing_context」**没有代码层断言**，取决于 caller——sidecar 不能
   从「与 I1 相同」推出 scope 安全，必须靠 §1.1 的字段化 gate 自证；
2. sidecar 复验的是 I1 所用的那个**充分条件**（纯 binding 不可行），不是
   生产全部 binding/routing exhaustion 形态本身。sidecar 报告必须保留
   `proof_stage`、exhaustion 标志与 scope 字段，I1 结论只作对拍矩阵第三腿。

对拍矩阵不变：生产 CP-SAT / I1（同构独立进程）/ sidecar（异构编码+异构
求解器+机器可查证明）。

## 2. 被复验模型的语义清单（v2 补全输入校验与边界）

`PortBindingModel`（`src/models/binding_subproblem.py`）在
`PURE_BINDING_INITIAL` 形态下的语义分四层：输入 → 输入校验 → 变量/约束 →
边界行为。**输入校验与边界行为也是被复验语义的一部分**（v1 漏了大半）。

### 2.1 输入（全部可从冻结工件 + 布局候选重建）

- `placement_solution`：instance_id → {facility_type, pose_idx}；
- `facility_pools`：facility_type → pose 列表（pose 含 `input_port_cells` /
  `output_port_cells`，每 cell {x,y,dir}）——源头 `mandatory_exact_instances.json`
  + `candidate_placements.json`（冻结）；
- `instances`（source_instances）：instance 元数据（operation_type 等）；
- `required_generic_outputs` / `required_generic_inputs`：commodity → 精确槽数
  （`generic_io_requirements.json`，冻结）；
- `wireless_sink_generic_input_slots`：`preprocess_plan.json`
  `utility_operations.wireless_sink.generic_input_slots`（冻结）；
- canonical `commodity_metadata`（`canonical_rules.json`，冻结）——参与
  角色校验（v1 漏项）。

### 2.2 输入校验（sidecar 必须在发 OPB 前独立复现；失败 = `INPUT_INVALID`，不得编码为 UNSAT）

1. **generic I/O 规范化与角色校验**：
   - `"__unused__"` 是保留 sentinel，禁止出现在需求工件；
   - 槽数必须是非 bool 的整数且非负；
   - 每个 required generic **output** commodity 必须在
     `canonical_rules.commodity_metadata` 存在且 `source_kind == "external_boundary"`；
   - 每个 required generic **input** commodity 必须存在且
     `sink_kind == "generic_input"`；
   - **完备性**：只要 generic I/O 需求非双空，canonical 中所有
     `sink_kind == "generic_input"` 的 commodity 必须以**正槽数**出现在
     `required_generic_inputs`（漏声明/零槽数 = 生产 ValueError）。
2. **wireless_sink K**：非 bool 整数且非负。
3. **placement/instance 元数据**（生产 `_validate_placement_instance_metadata` +
   `_resolve_instance` 语义）：
   - `ghost_pick` 是非设施 marker，完全跳过；
   - **pose_optional 合成**（v1 转述不完整）：placement 中缺 metadata 的 id，
     先用 `sol["facility_type"]` 查 `POSE_OPTIONAL_OPERATION_BY_TEMPLATE`
     （={protocol_storage_box→wireless_sink, power_pole→power_supply}）；
     **未命中且 `instance_id.startswith("pose_optional::")` 时，从
     `instance_id.split("::")[1]` 反推模板再查映射**；仍未命中 → 记
     `missing_instance_ids` → INVALID_INPUT 路径；
   - metadata 一致性：solution facility_type 缺失、pose_idx 缺失/bool/不可转
     int/越界、instance facility_type 缺失或与 solution 不匹配、canonical
     facility 的 operation_type 缺失/未知/与 profile facility_type 不匹配——
     任一命中 → 生产 `solve()` 返回 `INVALID_INPUT`（不调用 CP-SAT）。
4. **build 期 raise 边界**：生产 build 在 solve 前执行，可能直接抛异常——
   `_resolve_pose` 的 pose_idx 越界 IndexError、`sol["facility_type"]` KeyError、
   以及域枚举的「侧内所需槽数 > 物理 port cells 数」ValueError。sidecar 对
   这类输入输出 `INPUT_INVALID`（子码 `PRODUCTION_EXCEPTION_CLASS`），
  **不得把它们编码成 `EMPTY` 或计数 UNSAT**。

### 2.3 变量与约束（三个互不耦合的组；I1 形态）

A. **binding 域组**（per instance，`supports_exact_pose_level_binding(op)` =
   profile 的 generic hub slots 全零）：
   - 域 = operation profile 的 `input_slots`/`output_slots`（commodity→槽数，
     由 `_rate_to_slots` 从 PreprocessContext 推导）分配到 pose 物理 port cells
     （按 (x,y,dir) 排序）的全部组合，两侧笛卡尔积；
   - |域|=1 → 无变量（fixed choice）；|域|>1 → BoolVar + **ExactlyOne**；
   - 域空 → 生产加 `0 == 1`。
B. **generic output 槽组**（operation_type ∈ {boundary_io, protocol_core}，
   该集合是**生产源码硬编码**——TCB 声明见 §3.3）：每 output_port_cell 一槽，
   每槽对 (required outputs 的 commodities + `__unused__`) ExactlyOne；
   每 commodity 精确计数等式（见 §3.2 REQ/ZERO 的唯一化）。
C. **generic input 槽组**（operation_type == wireless_sink）：每 instance
   K 个虚拟槽（无物理坐标），同 B 的 ExactlyOne + 计数。
D. 搜索指导（DecisionStrategy/FIXED_SEARCH）不影响可满足性，不编码。

### 2.4 结构推论（v2 修正——v1 的「两类穷尽」错了一半）

在 `routing_context=None` 的 Phase 1 纯模型中，**域枚举不会返回空域**：
「槽数超 cells」是 raise（属 §2.2-4 边界），无 required slots 时返回单一空
pattern（非空域），两侧 product 非空。`EMPTY(i)` 分支在当前源码下只能由
routing-aware 过滤触发——而那是 `OUT_OF_SCOPE`。

⇒ **Phase 1 真实可达的纯 binding UNSAT 来源 = generic input/output
精确计数系统不可满足**（本质鸽笼/计数矛盾）。`EMPTY(i)` 约束族保留（防御
未来枚举器语义变化 + emitter 单元测试用），但**不计入 production-aligned
验收覆盖**（§6）。UNSAT 证明预期很小（cutting-planes 计数论证），符合
PoC「链路先通、深度后来」定位。

## 3. PB 编码规格（独立重建侧）

### 3.1 变量映射（v2：结构化 varmap，禁 split 解析）

- `b(i,k)`：instance i 选 binding pattern k（仅 |域|>1）；
- `s(slot,c)`：槽 slot 分配 commodity c（含 `__unused__`）。
- 编号确定性：按 (instance_id 字典序, k) 再 (slot_id 字典序, commodity 生产序
  ——真实 commodity 字典序 + `__unused__` 恒最后) 分配。
- `varmap.json` 每变量是**结构化对象**（instance_id 可含 `::`，slot_id 形如
  `{instance_id}:in:{n}`——**禁止任何 split 字符串解析**）：
  - binding：`{"kind":"binding_choice","instance_id":…,"binding_idx":k}`
  - slot：`{"kind":"generic_input"|"generic_output","slot":{"slot_id":…,
    "instance_id":…,"direction":"in"|"out","local_idx":n},"commodity":…}`
  `slot_id` 作兼容字段保留，checker/对账器只读结构化字段。OPB 内仍只用 `x1..xN`。

### 3.2 约束族（v2：REQ/ZERO 唯一化 + 零项规范化 + NOGOOD 改材料化语义）

| 族 ID | 形式 | 触发条件 |
|---|---|---|
| `EXO-BIND(i)` | Σ_k b(i,k) = 1 | \|域\|>1 的 instance |
| `EMPTY(i)` | canonical false row | 仅当生产枚举真返回空列表（Phase 1 实际不可达，见 §2.4） |
| `EXO-SLOT(slot)` | Σ_c s(slot,c) = 1 | 每已物化槽 |
| `REQ-OUT(c)` / `REQ-IN(c)` | Σ_slot s(slot,c) = required_c | **仅 required_c > 0** |
| `ZERO-OUT(slot,c)` / `ZERO-IN(slot,c)` | s(slot,c) = 0 | **仅 required_c = 0**，逐槽逐变量（生产语义：不发 sum 行）；无变量则不发约束、记零变量计数 |
| （Phase 1.5+）`NOGOOD(j)` | Σ_{l∈L_j} l ≤ \|L_j\|−1 | L_j = 生产**实际材料化**的 literal 集 |

**NOGOOD 语义修正**（v1 的「平凡扩展」是错的）：生产 `add_nogood_cut(selection)`
只收集模型中**真实存在的 BoolVar**——fixed binding choice（|域|=1）无变量、
不进 cut；不存在的 slot/commodity 被忽略；literal 集为空则**不加约束**。
⇒ Phase 1.5 若编码 nogood，采集必须保存每次 cut 的实际 literal 列表（或足以
独立复算的 var-existence 证据）；按 selection 全量编码会比生产更强 = 漂亮假证。
无法复算 L_j 的样本 `OUT_OF_SCOPE`。

**零项规范化**（emitter/witness checker/`#equal` 计数共享同一 OPB-row 规范，
但不共享高层约束生成代码）：`EMPTY(i)` 用固定 false row 并在 conmap 标
`constant_false`；`Σ_empty = 0` 不输出约束；`Σ_empty = k>0` 输出 canonical
false row 并标 `empty_sum_required_positive`。

约束 ID：OPB 行序确定性，`conmap.json` 记 (行号 ↔ 族 ID + 参数 + 是否等式)。

### 3.3 独立重建边界与语义 TCB（v2 重写：三层来源显式化）

「不 import `src/`」只是最低要求。Phase 1 前必须建立
`binding_canonical_semantics_v1` 规范文件，把每条语义标注来源层：

1. **冻结数据语义**（从冻结字节可复算）：strict JSON 解析行为（拒重复
   key/NaN/Infinity——独立重实现 + golden fixtures）、generic I/O 数值与角色
   校验、wireless_sink K、operation profile 的 rate→slots 推导（从
   preprocess_plan + canonical_rules 独立重推）、facility_pools 重建、
   域枚举组合数学、槽物化、全部约束生成。
2. **生产源码硬编码语义**（业务常量，不在冻结工件里）：
   `POSE_OPTIONAL_OPERATION_BY_TEMPLATE` 映射、`ghost_pick` marker 集合、
   generic output provider 集合 {boundary_io, protocol_core}、generic input
   receiver 集合 {wireless_sink}、`supports_exact_pose_level_binding` 的
   gate 定义。**sidecar 只能手抄这些常量 ⇒ 它们属于 sidecar 与生产共享的
   TCB**：报告必须显式声明 `not independently checked by Phase 1`，不得把
   这些项宣传为 sidecar 的防护面。中期出路 = 把它们提升进 canonical schema
   （登记为 Phase 0 工作项）。
3. **核对源完整性前置条件**（v1 实犯——`operation_profiles.py` 与
   `strict_json.py` 未入审查包却被口头规格化）：实现开工前，
   `src/preprocess/operation_profiles.py`、`src/io/strict_json.py`、
   facility_pools 装配源码必须补进核对材料并逐行规格化进
   `binding_canonical_semantics_v1`；缺核对源期间相关样本只能
   `SPEC_INCOMPLETE`，不得 `CONFIRMED`。

### 3.4 输入采集：canonical sample record（v2 重写——dump 降级为 fixture）

**v1 的「直接消费 dump」违反独立重建**：`EXACT_BINDING_DUMP_STATE` 的 dump
产生于 `PortBindingModel.__init__` 之后（pose_optional 已合成、requirements
已规范化）、`solve()` 入口之时（无 verdict/ordinal/scope），是**生产加工后
的世界**。把它当权威输入 = 复验生产自己的输出。

**修正**：Phase 1 可 `CONFIRMED` 的样本必须是 `binding_sidecar_sample_v1`
记录，至少含：
- `sample_id`（run id + iteration + `binding_solve_ordinal` + placement hash
  + artifact hash bundle 组成）；
- `production_solver_status`（本次 solve 的最终生产 verdict）；
- `binding_scope_class`（§1.1；Phase 1 只收 `PURE_BINDING_INITIAL`）
  及其证据字段：`solve_ordinal==0`、`rejected_selection_count==0`、
  `routing_context_enabled==false`、`overload_separation_enabled==false`；
- `artifact_hashes`：五个冻结工件的**全长** sha256；
- `facility_pools_sha256`（**全长**，含 canonicalization 版本）：sidecar 从
  冻结工件重建 pools 后必须复算相等，不等/缺失 → `INPUT_MISMATCH`，不解不判；
- `placement_solution` 与原始 `source_instances`（**原始输入**，非模型内部
  `instances_by_id`）的 canonical JSON hash；
- `producer_code_version` + schema version。

现有 dump（schema v2：16-hex signature、无 verdict、加工后 instances）
**只能当合成/调试 fixture 与审计对照**；在无 canonical sample record 的
真实样本上，Phase 1 只输出 `NOT_REPLAYABLE`，不做生产对账。dump 字段与
sidecar 独立重建结果不一致 → `INPUT_DIVERGENCE`（审计信号，非 CONFIRMED 路径）。
placement hash 只是辅助索引，不得作 verdict 关联唯一键。

> 采集侧改造（给 dump 加 verdict/scope/ordinal 字段或新增 sample record 写出）
> 动生产文件，**属 Phase 0 工作项、需 owner 单独批**——Phase 1 期间先用合成
> 样本 + 缩小版 exhaustive fixtures 完成验收（§6），不阻塞。

## 4. 求解与检查链（WSL 侧，2026-07-05 已实测跑通）

```
emitter(Win, py3.13, 零 import src/) → instance.opb + varmap.json + conmap.json
  → WSL: roundingsat instance.opb --proof-log=<path>
  → WSL: veripb [--force-checked-deletion] instance.opb <path>
  → 对账器(Win): scope gate → 四值判定 → 工件归档(argv/stdout/stderr/sha256 全量)
```

工具链硬规格（全部 2026-07-05 源码+实验坐实，详见 `toolchain_notes.md`）：
- RoundingSat master d4edbf7 本地编译（WSL Ubuntu 24.04，GMP/Boost/zlib）；
- VeriPB 3.0.2 = **Rust 主线**（`cargo install`；深研报告「Python 参考版」
  口径过时；CakePB 对接口 = `veripb --elaborate`，Phase 1 后续）；
- **扩展 OPB 头（硬规格，v1 的 §4/§7 矛盾在此收口）**：
  `* #variable= N #constraint= M #equal= K intsize= 0`——N=变量数，M=约束行
  总数，**K 必须精确等于使用等号的约束行数**（EXO-BIND、EXO-SLOT、正 REQ、
  ZERO 逐变量等式计入；EMPTY false row 与 NOGOOD 不等式不计入），因为 proof
  logger 按「等式占两个约束 ID」初始化计数；K 写错属 fail-detect（solver 照出
  proof、veripb 必拒，实验已双向坐实）。intsize 被 parser 吞掉不参与语义，恒写 0；
- proof 文件 = `--proof-log=<path>` 的 path 本身；格式 version 2.0，
  veripb 3.0.2 向后兼容；
- RoundingSat UNSAT 退出码为 1（**runner 禁用 `check=True`**）；
  veripb 失败退出码仍为 0（**禁用退出码判定**）。

## 5. 判定协议（v2 加硬：fail-closed + 状态码细化 + 护栏前置）

### 5.0 前置护栏（发 OPB 前，顺序执行）

1. **scope gate**（§1.1/§3.4）：非 `PURE_BINDING_INITIAL` 或字段缺失/矛盾 →
   `OUT_OF_SCOPE`；hash 不匹配 → `INPUT_MISMATCH`；
2. **输入校验**（§2.2）：失败 → `INPUT_INVALID`（生产 raise 类子码
   `PRODUCTION_EXCEPTION_CLASS`）；
3. **组合规模预估**（v1 §7.5 提前进协议）：逐 instance 算两侧 pattern 数及
   乘积、逐槽组算变量/约束数；任一超配置上限 → `UNKNOWN` 子码
   `EMITTER_DOMAIN_TOO_LARGE`，**不产生 partial OPB/proof 工件**；上限、
   估算值、触发 instance 写入报告。sidecar 可自建 cache，但 cache key 与
   命中审计输出；生产 cache 行为不作为正确性依赖。

### 5.1 CONFIRMED（异构确认不可行——六条全满足，任一不满足降级）

1. RoundingSat 进程完成未被 kill；stdout 解析到**唯一一行**完全匹配
   `^s UNSATISFIABLE\s*$`，且不存在任何其他 `^s ` status 行（冲突行 →
   `TOOL_PROTOCOL_ERROR`）；
2. proof 文件存在、regular、非空，mtime 晚于 solver 启动，sha256 记录；
3. veripb 调用显式传本次 OPB path + proof path；argv、两文件 sha256、
   stdout/stderr、exit code、工具版本全量归档；
4. veripb stdout 解析到**唯一一行**完全匹配 `^s VERIFIED UNSATISFIABLE\s*$`；
5. veripb stdout/stderr 无 `Error:` / `Checking error` / `panic` /
   `unsupported` 类拒绝标志（warning 记录、非白名单不自动 PASS）；
6. checker 输出与本次 OPB/proof sha256 对上（否则 `PROOF_NOT_CONSUMED_OR_STALE`）。
   严格模式 `--force-checked-deletion`。

### 5.2 SIDE_SAT / DIVERGED_CANDIDATE（v2 降级命名——不再叫 DIVERGED）

RoundingSat 出 SAT 时：
1. **OPB-level witness check**：只读 instance.opb + varmap + assignment 逐行
   验约束（**不调用 emitter 的约束生成函数**）；不过 → `SIDE_SAT_UNTRUSTED`；
2. **canonical-level witness check**：按 `binding_canonical_semantics_v1`
   从原始输入独立重算（域 membership、槽物化、计数、校验）；通过 →
   `DIVERGED_CANDIDATE`（「sidecar 找到满足独立语义规格的 witness，与生产
   INFEASIBLE 冲突」——**不得自动归因生产 bug**，报告必须给
   production-bug / emitter-underconstraint / checker-bug 三分类 triage）；
   canonical checker 未实现或未通过 → `DIVERGED_OPB_ONLY`；
3. witness checker 自身验收：known-feasible canaries、非法 witness、
   slot/commodity 错配、fixed-choice、pose_optional 各类红测通过前，
   本路径不作结论性状态。

### 5.3 其余状态

`UNKNOWN`（子码 `SOLVER_STATUS_UNPARSEABLE` / `PROOF_NOT_CONSUMED` /
`PROOF_REJECTED` / `TOOL_CRASH` / `EMITTER_DOMAIN_TOO_LARGE` / timeout）、
`OUT_OF_SCOPE`、`INPUT_INVALID`、`INPUT_MISMATCH`、`INPUT_DIVERGENCE`、
`NOT_REPLAYABLE`、`SPEC_INCOMPLETE`。

**语义纪律**（不变）：sidecar 全部输出是 diagnostic 对账信号，不是认证证据——
不写 proof 路径、不影响任何 gate/status。升格须走 owner 拍板 + 锁面变更流程。

## 6. 验收判据（v2 重写：覆盖矩阵 + 双向红测 + FEASIBLE canaries）

「20 个 INFEASIBLE 全 CONFIRMED」不是充分条件（它抓不住 over-constraint——
过约束的 emitter 在一切 INFEASIBLE 样本上都会漂亮 CONFIRMED，然后把真实可行
也证成 UNSAT）。Phase 1 验收 = 五件套：

1. **Scope gate 样本**：`PURE_BINDING_INITIAL` 可进；routing-aware / overload /
   rejected-selection / 缺关联键 / pools hash mismatch 各至少一例，全部必须
   `OUT_OF_SCOPE`/`INPUT_MISMATCH`，不得 CONFIRMED。
2. **正向 UNSAT**：≥20 个 `PURE_BINDING_INITIAL` 对齐样本（合成 + 缩小版
   fixtures），每个标注 UNSAT 来源类（generic output 计数 / generic input
   计数 / 其他）；`EMPTY` 类只有生产在 Phase 1 scope 下实际可达时才计入
   （当前源码下不可达，见 §2.4——手搓 EMPTY fixture 只算 emitter 单元测试）。
3. **正向 FEASIBLE canaries**：≥20 个已知可行样本（覆盖 fixed 域/多元域/
   generic in+out/pose_optional/zero requirements/双空 requirements），
   sidecar 必须 SAT 且双层 witness check 通过。**任何 canary 被证 UNSAT = BLOCK。**
4. **Exhaustive 小模型**：缩小版 fixtures 上穷举 placement/requirements 组合，
   对拍 production CP-SAT、canonical evaluator、PB 链三方的
   SAT/UNSAT/INPUT_INVALID 三值一致性。
5. **双向红测矩阵**（每类至少一例，预期结果按方向判）：
   - under-constraint（应 UNSAT 变 SAT）：漏 EXO-SLOT、REQ 放宽、漏
     provider/receiver 过滤、漏 `__unused__`；
   - **over-constraint（应 SAT 变 UNSAT——用 canaries 抓）**：漏槽、K−1、
     fixed choice 错编成 hard literal、raise 错编成 EMPTY、误加
     routing-aware/overload 类约束、额外 ZERO、`supports_...binding` gate 收窄；
   - mapping：slot/commodity/instance 串位（含 `pose_optional::…` id）、
     varmap 错位；
   - input-boundary：`__unused__` 入需求、bool/负槽数、canonical role 不符、
     generic input 完备性漏项、非法 pose_idx、pose_optional 漏合成/误合成/
     反推误解析；
   - toolchain：proof 篡改、实例-证明错配、旧 proof、错 `#equal`、空 proof、
     缺 proof、SAT 实例配 UNSAT proof（全部不得 CONFIRMED）。
6. **预算**：单样本全链 wall-clock 进 nightly 预算（初验标尺 <60s/样本，
   超了记录调整）。样本数只是 smoke baseline，验收以矩阵覆盖 + mutation
   kill rate + exhaustive 一致性为准。

## 7. 开放问题（v2 清理后）

1. **Phase 0 canonical sample record 的落地形态**：给生产 dump 加
   verdict/scope/ordinal（改 `_maybe_dump_state`）vs 新增独立采集器——动生产
   文件，需 owner 批准与排期（对应 roadmap Phase 0「canonical 子问题格式」）；
2. **形态②（REJECTED_SELECTIONS_ACCUMULATED）的材料化 literal 采集**：
   依赖 1 的 schema 扩展；
3. proof version 2.0 → 3.0 / CakePB elaborate 链路的版本面（Phase 1 收尾时核）；
4. `binding_canonical_semantics_v1` 中硬编码常量层（§3.3-2）提升进 canonical
   schema 的路径与时点；
5. witness checker 的正确性背书长期方案（红测 + 将来 Lean 化，轴 A 潜在对象）。

## 8. 与既有防线的关系

```
生产 CP-SAT INFEASIBLE
   ├─ I1 独立 CP-SAT 复验（同构、已在生产链）        ← 防「seal 前的偶发错」
   └─ PB sidecar（本稿，异构+证明日志，离线 nightly） ← 防「builder 语义性错」
        │   覆盖面按 §3.3 诚实declare：冻结数据语义层可防；
        │   生产硬编码常量层与生产共享，Phase 1 防不了（显式 TCB）
        └─ VeriPB checker（第三方，Rust）             ← 防「第二求解器也错」
             └─ CakePB（形式化验证，Phase 1 后续）     ← 防「checker 也错」
```
与 PR2 #5-B2、I1 是同一笔投资的三个面，同打「编码忠实性单点」。

## 9. v1→v2 修订记录（双会话对抗审回收，两份均判 REJECT 后重写）

| # | v1 问题（审查指认） | v2 处置 |
|---|---|---|
| 1 | dump 当权威输入，破坏独立重建（双方 BLOCK） | §3.4 重写：canonical sample record；dump 降级 fixture；`NOT_REPLAYABLE`/`INPUT_DIVERGENCE` |
| 2 | scope 非机器闭合，「两形态」分类不成立（双方 BLOCK） | §1.1 重写：五分类 `binding_scope_class` + 字段化 gate |
| 3 | 漏 generic I/O 角色/完备性校验（BLOCK） | §2.2-1 补全 |
| 4 | 漏 metadata 校验边界；INVALID_INPUT/raise/UNSAT 混同（BLOCK） | §2.2-3/4 补全 + `PRODUCTION_EXCEPTION_CLASS` |
| 5 | pose_optional 反推规则漏转述（BLOCK） | §2.2-3 补 `::` 反推 |
| 6 | operation_profiles/strict_json 未入核对源（BLOCK） | §3.3-3 前置条件 + `SPEC_INCOMPLETE` |
| 7 | 硬编码常量被当独立重建项（BLOCK） | §3.3 三层来源；共享 TCB 显式声明 |
| 8 | I1「相同对象」过度声称（双方） | §1.2 修正（kwargs 透传无 routing_context 断言） |
| 9 | 「域空」当主要 UNSAT 来源——实为死分支（CONCERN） | §2.4 结构推论重写；EMPTY 不计验收覆盖 |
| 10 | nogood「平凡扩展」错误（双方） | §3.2 材料化 literal set 语义 |
| 11 | §4/§7.3 header 自相矛盾（双方） | §4 硬规格收口，§7.3 删除 |
| 12 | 判定协议不够硬（双方） | §5.1 六条 anchored/唯一行/sha256/mtime/argv 归档 |
| 13 | DIVERGED 半信任不自洽（双方） | §5.2 降级 SIDE_SAT/DIVERGED_CANDIDATE/DIVERGED_OPB_ONLY + triage 三分类 |
| 14 | 红测缺 over-constraint + FEASIBLE canaries（双方 BLOCK） | §6 双向矩阵 + canaries + exhaustive 小模型 |
| 15 | 20 样本无统计意义 | §6 覆盖矩阵为准 |
| 16 | 组合爆炸防护应进协议 | §5.0-3 前置护栏 |
| 17 | ZERO/REQ 双发歧义 | §3.2 唯一化（生产语义：required=0 不发 sum） |
| 18 | 零项约束 OPB 表达 | §3.2 零项规范化 |
| 19 | varmap split 解析歧义 | §3.1 结构化对象 |
| 20 | 16-hex signature 不够 | §3.4 全长 sha256 + `INPUT_MISMATCH` |
| 21 | `__unused__` 排序 / 文件名引用 / 红测计数 NIT | §3.1 生产序；`toolchain_notes.md`；§6 双向矩阵取代计数 |
