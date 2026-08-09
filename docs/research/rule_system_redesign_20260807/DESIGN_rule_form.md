# 规则形态改造设计 — canonical 分层、条目形态与派生闭包承载

**日期**：2026-08-07　**席位**：规则形态轨设计席　**状态**：设计稿，待 owner 裁决三项（§9）
**一句话现状**：给出四层分层方案（求解器事实层 / 裁决层 / 派生闭包层 / 投影视图层）与各层条目形态；三个改造选项比较后推荐「投影视图层先行 + 裁决层三批 additive 收紧 + 否决整体重排、只吸收其实体镜像片段」；本文只出规格，未改任何被钉文件。

**输入**：同目录 `failure_taxonomy_and_requirements.md`（52 病例 / R-01…R-33 需求 / K-1…K-8 约束）与 `canonical_anatomy.md`（结构解剖）。本文的所有仓库事实由本席现场机器核实，命令与结果见附录 A；与两份输入不一致处在正文标出（§2.2 一处）。

**施工边界**：只读仓库，只写本文件。所有落地动作（改 canonical、改 schema、新增脚本、改 pin）由后续 freeze-ritual 批执行。

---

## 0. 这份文件解决什么

owner 08-07 的两枪与随后的闭包公理，指向同一个形态问题：**规则的载体没有位置放「使这条规则成立的东西」，也没有位置放「从这条规则推出来的东西」。**

- 第一枪（协议箱堵塞判据不可达）：判据在一条条目里，判定它可达所需的六个参数散在三个顶层分区、四种表达形态，其中一个（单槽容量）在文件里不存在。载体没有「参数回链」位，也没有「界可达性」位。
- 第二枪（`rate_lemma_scope` 欠台间占空均摊前件）：前件以散文 `(i)(ii)` 列举，没有完备性装置。载体没有一等前件位。
- 闭包公理：基础规则不断组合出次级规则，某些组合把解空间压塌成新规则的结晶点。载体根本没有派生规则的位置——派生规则今天散落在 `.artifacts/` 与 `docs/research/` 的批次文书里，没有前提集、没有层级、没有失效机制。

本文回答三件事：**层怎么分**（§1）、**每层的条目长什么样**（§2）、**改造怎么走**（§3、§6）。另加两个被点名的专项：过严面登记升格（§4）与能力盘点对账（§5）。

---

## 1. 分层方案

### 1.1 四层

| 层 | 内容 | 载体 | 权威来源 | 变更代价 | 失效语义 |
|---|---|---|---|---|---|
| **L0 求解器事实层** | `globals` / `facility_templates` / `recipes` / `production_targets` / `commodity_metadata` | `rules/canonical_rules.json`（现有分区，本设计不动其字段集） | owner 游戏实测 > 模拟器规则层 | 最高：改一个字段即触发派生工件重生成 + schema + pydantic + 派生工件 pin | 不失效，只被取代 |
| **L1 裁决层** | 公理 A1–A11、owner 裁决、作用域声明、条目化的规则语句、**实体参数镜像**、**过严/过松面登记** | `rules/canonical_rules.json` 的 `semantics` 分区（改造对象） | owner 裁决 / 公理 | 中：canonical sha 变 ⇒ 固定 reseal 连锁（§3.1），但零派生工件重生成 | 不自动失效，只被显式取代 |
| **L2 派生闭包层** | 由 L0+L1 组合推出的次级规则、定理、界、结晶点、不可达性结论 | 新文件 `rules/derived/derived_rules.json`（tracked，**不进 `FROZEN_ARTIFACTS`**） | 前提集 + 推导 + 可复跑收据 | 低：改它不动 canonical sha，不触发任何 pin 链 | **自动失效**：前提指纹与现场重算不符 ⇒ `STALE` |
| **L3 投影视图层** | 实体参数表、参数反向索引、条目-谓词矩阵、过严面台账、能力覆盖率表、闭包图 | `docs/generated/`（tracked，可重生） | **无**——非权威，每个数字带它的 L0/L1/L2 出处路径 | 零：生成器重跑 | 由 currency 测试强制与源同步 |

### 1.2 为什么派生层不能进冻结文件

三条理由，都可从仓库现状直接核到：

**(1) 节拍不匹配，混进去等于关掉闭包扫描。** canonical 的 sha 一变，reseal 连锁的固定成本就要付一次（17 处直接 pin + 三条连锁链，§3.1）。闭包扫描的产出形态是「一次扫出一批候选派生规则，其中多数很快被证伪或被更强的条目取代」——这种高频、可撤销的产出如果每条都要付一次 freeze-ritual，实际结果是没有人跑扫描。这正是 `slow-for-safety-can-be-slow-death` 那条判据在治理层的复现：结构性走不完的保守支不是真选项。

**(2) 权威等级不同，混排必然重演证据等级混用。** 裁决层的权威是 owner 实测（不可复跑，只能对账）；派生层的权威是前提集加推导（可复跑）。C-32 的四轮根因定谳是「勤奋全落在可复跑层，复跑的踏实感掩护未查的前提」。把两类放进同一个文件、同一种字段形态，读者无法从位置判断手上这一条是被实测过的还是被推出来的——分层本身就是这条纪律的物理实现。

**(3) 冻结文件表达不了「自动失效」。** 派生条目的核心生命周期事件是「我的某条前提变了，所以我失效了」。冻结文件只有字节相等/不等这一种状态，没有条目级的失效表达位，也没有触发失效的时机（改 canonical 的人不会顺手把所有引用了旧参数的定理标成 STALE）。L2 用前提指纹 + currency 测试把这件事做成机器动作（§2.3）。

**推论**：L2 不进 `FROZEN_ARTIFACTS`，但它**不是自由文本**——它有 schema、有 currency 测试、有形态 checker，只是不参与 canonical 的 pin 继承链。

### 1.3 层间接口（谁能引用谁）

```
L0 参数  ──────┐
               ├──► L2 派生条目（前提集只能指向 L0 / L1 / 更低层级的 L2）
L1 裁决/公理 ──┘         │
                         └──► L3 视图（只投影，不新增事实）

L1 条目可以引用 L2 条目吗？可以，但只能通过「晋级」：
   L2 条目被 owner 裁决或被外审定谳后，其结论以 additive 方式写进 L1，
   同时 L2 原条目标 status=PROMOTED 并指向 L1 路径。
   禁止 L1 条目直接把一个活的 L2 条目当前提——否则冻结层的正确性挂在
   非冻结层上，重演 C-28（论证支点落在待变更面上、无登记位）。
```

**认证边界的机器化表达**（K-7）：L2 条目必带 `scope`。`scope != "certified"` 的条目**不得**出现在任何认证链文书的承重前提里；`scope == "certified"` 的条目必须其前提集里每条前件的 `dischargeable_in` 都包含 `certified`。这一条同时封死 C-25（certified 语境下不可 discharge 的引理被用来支撑 certified 放开）。

---

## 2. 条目形态规范

### 2.1 裁决层条目（`semantics.<clause>`）

必填字段集（schema `required` + `additionalProperties: false`）：

| 字段 | 形态 | 作用 | 对应需求 |
|---|---|---|---|
| `id` | `CLS-<slug>` | 稳定标识，供 L2 前提集与反向索引引用 | R-04 R-23 |
| `statement` | 单句结论，**当前真相**（被收窄时原地改写） | 单读即得当前结论 | R-08 |
| `superseded_readings[]` | 旧读法 + 作废日期 + 作废原因 | 保史料但不再能被误读为现行 | R-08 R-13 |
| `scope` | `certified` / `p2_0_flow` / `narrative` | 语义层不混写 | R-14 K-7 |
| `predicate_status` | 六谓词之一 / `non_predicate` / `enabling_premise` | 13/13 全覆盖，取代从 `applies_to` 猜 | R-10 |
| `applies_to_*` | 拆三个字段：`applies_to_paths[]`（文件内路径）、`applies_to_external[]`（外部工件路径）、`applies_to_predicates[]`（谓词名，取自闭合枚举） | 现状同一字段混三个命名空间，无法统一解析 | R-10 R-04 |
| `parameters[]` | 每项 `{ref, kind, value_at_write}`，`ref` 是 `globals.*` / `semantics.entities.*` 的机器可解析路径 | 散文数字禁止：条目里出现的每个量必须有回链 | R-04 R-05 |
| `premises[]` | 见下 | 前件一等公民 | R-01 R-02 |
| `reachability` | 见下（判据形态条目必填） | 界可达性注记 | R-03 R-20 |
| `direction` | `stricter` / `looser` / `exact` / `not_assessed`；非 `exact` 时必须给 `face_ref` 指向 §4 的登记条目 | 双向保真 | R-06 |
| `derivation` | `{kind: axiom_derived / owner_ruling / simulator_verified, refs[]}`；`axiom_derived` 时 `refs` 指向内置的推导编号表 | 8/13 覆盖率补齐；11 个悬空 `#N` 引用落地 | R-11 |
| `provenance` | `{decided_on, authority_level, method, source_doc, supersedes[], clarifies[]}` | 收敛现有七个做同一件事的字段 | R-09 |
| `consumers[]` | 反向引用（谁把这条当前提） | 改一条能机械求出受影响集 | R-23 R-27 |
| `usage_rule` | 可选；引用本条的合法方式 | 现状全文唯一一条，保留并推广 | — |

**前件项（`premises[]` 的元素）**：

```
{
  "id": "P-1",
  "statement": "满产（所有 recipe-backed operation 以 x_op 运行）",
  "kind": "parameter | axiom | ruling | convention | assumption | derived",
  "authority_kind": "owner_in_game | simulator_rule_layer | canonical_text | derivation",
  "dischargeable_in": ["p2_0_flow"],
  "not_dischargeable_in": ["certified"],
  "discharge_evidence": "…路径或 MISSING"
}
```

`kind: convention`（约定类前件）是专门为两次实锤开的位：C-14 的「最小车道分配约定」与 C-15 的「台间占空均摊约定」都属于这一类——**作者以为自己在陈述事实，实际是在选一个分配**。schema 层做不到「保证前件完备」，但可以做到两件有界的事：①约定类前件必须显式标 `kind: convention`；②形态 checker 断言——凡 `statement` 或 `derivation` 中出现分配/取值/摊派语义的算术，`premises` 里必须至少有一条 `kind: convention` 或 `kind: assumption`，否则红。这不能证明前件集完备，但把「一条约定被当成事实、连自己是选择都没意识到」这个具体形态挡住了。

**可达性块（`reachability`）**：凡 `statement` 含「当且仅当 / exactly when / blocks when / triggers when / fails when」形态判据的条目必填。

```
{
  "condition": "6 个缓存槽同时全占",
  "parameters": ["semantics.entities.protocol_storage_box.physical_inputs",
                 "globals.logistics.port_max_throughput_per_tick",
                 "globals.time.tick_interval_seconds",
                 "semantics.entities.protocol_storage_box.flush_period_seconds",
                 "semantics.entities.protocol_storage_box.slot_count",
                 "semantics.entities.protocol_storage_box.slot_capacity"],
  "verdict": "unreachable | reachable | conditional | NOT_ASSESSED",
  "computation": "3 口 × 1 件/tick ÷ 2.0 s × 10 s = 15 件/冲刷周期 vs 容量 6×50 = 300 件",
  "assessed_on": "2026-08-07",
  "receipt": "docs/research/…/…py"
}
```

`verdict: NOT_ASSESSED` 是合法值但**不是免死金牌**：形态 checker 对 `scope: certified` 且 `direction: stricter` 的条目禁止 `NOT_ASSESSED`（一条更严的、危险条件没核过的规则，正是 C-17 的完整画像）。

### 2.2 实体参数镜像（`semantics.entities`）

新增子分区，每个实体一个条目，字段固定：

```
"protocol_storage_box": {
  "template_ref": "facility_templates.protocol_storage_box",
  "geometry":        {"w": 3, "h": 3, "rotatable": true, "is_solid_z": true,
                      "source": "mirror:facility_templates.protocol_storage_box"},
  "ports":           {"physical_inputs": 3, "physical_outputs": 3,
                      "port_rule": "opposite_parallel_sides",
                      "source": "owner_adjudicated:2026-08-06"},
  "port_rate_ref":   "globals.logistics.port_max_throughput_per_tick",
  "buffer":          {"slot_count": 6, "slot_capacity": 50,
                      "source": "simulator_extract:IndustrialPlanner@8da9017a"},
  "cycle":           {"flush_period_seconds": 10, "requires_power": true,
                      "source": "owner_adjudicated:2026-08-06"},
  "missing":         []
}
```

三条形态规则：

1. **`missing[]` 必填、可为空数组、不得省略。** 缺项写进 `missing`，不是不写。C-17 的单槽容量今天在 canonical 里根本不存在，最接近的是 `axiom_kernel.axioms.A7_rates` 里制造机的「one input buffer slot × 50 per ingredient」——一个极易被误取的邻居。有 `missing[]` 时，「这个量我们没有」是一条可枚举、可计数、可上报的事实。

2. **与 L0 重叠的字段是镜像，必须双向等值。** 形态 checker 断言 `geometry`/`port_rule` 与 `facility_templates` 逐字段相等，**两个方向都断言**（镜像里多一个字段、少一个字段都红）。C-36 的教训是「投影层比被镜像的权威层更严 ⇒ prod 潜伏 fail-closed」，其一般形式是「镜像与权威不等值就是定时炸弹」，所以这里不做单向包含，做等值。

3. **不与 L0 重叠的字段必须标 `source`**，取值域是权威序的闭合枚举（`owner_adjudicated` / `simulator_extract` / `mirror` / `derivation`）。

**为什么镜像放在 `semantics` 而不是直接扩 `facility_templates`**（这是本设计里代价最大的一个取舍，机器核实过）：

- `facility_templates` 的 schema 是 `additionalProperties: false` 且属性集封闭（`rules/canonical_rules.schema.json`），pydantic 侧 `FacilityTemplate(StrictBaseModel)`（`src/rules/models.py:119-129`）同样封闭。加一个字段 ⇒ 两处都得改。
- `preprocess_context` 把 `facility_templates` **整体 deepcopy** 进上下文（`src/interchange/preprocess_context.py:230`），并原样落进 tracked 派生工件 `data/solutions/current_preprocess_context.json`（实测：该文件里 `protocol_storage_box` 条目与 canonical 逐字节同形）。加字段 ⇒ 该工件字节必变 ⇒ `src/tests/test_preprocess_context.py`、`src/tests/test_regression.py` 连带改。
- 更要命的是**论证成本**：08-07 canonical 批之所以能便宜地走完，靠的是一句机器可验的安全论证——「8 个 solver 消费顶层段与 HEAD byte-identical，派生 preprocess 工件八段字节不变」（`docs/research/canonical_batch_20260807/DEPENDENCY_VERIFICATION.md`）。一旦动 `facility_templates`，这句论证当场作废，本批必须改用「重生成 + 逐字段比对」来证明派生工件正确，验收面从「字节相等」退化成「语义相等」。

- `semantics` 分区没有任何 solver 消费方（已核：`preprocess_context` 与 `material_skeleton` 只读 `globals.time` / `globals.logistics` / `facility_templates` / `recipes` / `production_targets` / `commodity_metadata`），pydantic 侧是 `Optional[Dict[str, Any]]`（`src/rules/models.py:184`）。所以镜像放这里，**代价是零派生工件变动**，而权威性不减——它同样在冻结字节里、同样受 owner 裁决管辖。

**对 `canonical_anatomy.md` §5 的一处订正**：该文把 `axiom_kernel.ruling_level_inputs` 称为「显式、闭合，形态良好」，可作为 R-07 的现成样板。实测该键是一个**普通 JSON 字符串**（散文），与 `model_stricter_faces` 结构上完全同型——它的「闭合」是内容层面的（散文里说清了「只有两条」），不是结构层面的。全文真正结构化的裁决样板是 `globals.empty_rectangle.emptiness_adjudication`：一个带 `required: [decided_on, authority, source_doc, statement]` 与 `additionalProperties: false` 的对象。§4 的过严面形态以它为样板，不以 `ruling_level_inputs` 为样板。

### 2.3 派生规则条目（L2）

```
{
  "id": "D-20260807-003",
  "level": 2,
  "kind": "theorem | bound | impossibility | unreachability | structural_feature | parameter_derivation",
  "statement": "免分流布局中，恰有一台制瓶机只用一个进料口",
  "scope": "p2_0_flow",
  "premises": [
    {"ref": "globals.logistics.belt_capacity_per_tick", "kind": "parameter", "value_at_derivation": 1.0},
    {"ref": "CLS-recipe-bottling", "kind": "parameter", "value_at_derivation": "2:1"},
    {"ref": "derived:D-20260806-011", "kind": "derived", "level": 1},
    {"ref": "objective:split_free", "kind": "assumption",
     "dischargeable_in": ["p2_0_flow"], "not_dischargeable_in": ["certified"]}
  ],
  "premise_fingerprint": "sha256(规范化前提集 || 每条前提的现场取值)",
  "derivation": {"method": "polytope_vertex_scan", "receipt": "…/receipt.txt",
                 "recompute_cmd": "python docs/research/…/recompute.py"},
  "crystallization": {
    "free_variable": "duty[bottling_op] ∈ [0,1]^6, Σ = 11/2",
    "collapsed_to": "d_i ∈ {1/2, 1}，其中恰一个取 1/2",
    "detector": "integrality_argument"
  },
  "direction": "neutral",
  "reachability": null,
  "status": "ACTIVE | STALE | RETIRED | SUPERSEDED | PROMOTED",
  "consumers": [], "sentinel": "src/tests/…::test_…"
}
```

四条形态规则：

1. **层级可机械计算**：`level = 1 + max(前提集里各前提的 level)`，L0 参数与 L1 条目的 level 记 0。这让「次级规则再与老规则组合出下一级」成为可枚举结构，也给饱和扫描一个终止判据（某一轮不再产出 level n+1 条目 ⇒ 该子空间对当前规则集饱和）。

2. **前提指纹驱动自动失效**：`premise_fingerprint` 覆盖前提集的路径与**现场取值**。currency 测试对每条 `ACTIVE` 条目重算指纹，不符即红，条目须重推或标 `STALE`。这是 C-03 那次一次性补的 source digest 的一般化（R-28），也是把「改一个参数，哪些结论作废」从人工三态账变成机器动作（R-27）的一半——另一半是 L3 的参数反向索引。

3. **结晶块是扫描的显式产出位，不是修辞**。`free_variable` 描述被压塌前的自由度，`collapsed_to` 描述压塌后的集合，`detector` 取自闭合枚举（`integrality_argument` / `polytope_vertex_scan` / `pigeonhole` / `capacity_vs_arrival` / `parity`）。检测器枚举是有界的，可以按类跑；这满足 K-4 的有界性要求（「查所有前提」「多审几轮」这类无界要求已被 C-15 证伪）。

4. **不可达性是一等 `kind`**。`kind: unreachability` 的条目专门装「某危险条件在当前参数下不可达」这类结论——这是 X-9 空档（限制永不报警 / 触发器永不触发）的正向承载位。协议箱堵塞判据与 cut 触发条件（C-34）都归这一类。

**饱和扫描的形态承载**（扫描纪律本身归推理流程轨；形态轨提供它需要的三个位）：

- L0/L1 条目的 `parameters[]` 与 `free_variable` 声明 ⇒ 给扫描器「受影响子空间」的输入；
- L2 的 `level` 与 `premise_fingerprint` ⇒ 给扫描器增量运行的基础（只重扫指纹变了的子图）；
- 扫描运行记录 `saturation_runs[]`：`{scope, started, rounds, new_entries[], terminated_by: "no_new_rules" | "budget"}`。**`terminated_by: budget` 的扫描不得被任何文书引用为「该子空间已饱和」**——与「零激活不等于 cut 无用」同一条纪律：预算删失的结论不是结论。

---

## 3. 三个改造选项

### 3.1 先看成本的真实形状

比较前必须先纠正一个直觉：**三个选项的 pin 成本几乎相同。** 只要 canonical 的字节变了一位，reseal 连锁的固定部分就要付满：

- 第一层直接 pin **17 处**：代码/测试 4 处（`scripts/preflight_gate.py:63` 大写 sha、`src/search/certified_artifact_contract.py:100` 小写 sha、`docs/research/witness_constructor_20260717/07_routing_aware/strict_contract.py:35`、`src/tests/test_w0_g1_generator_smoke.py:187`）+ 文档 13 处；
- 连锁 B（contract 字节变 → close-kernel V99 map → obligations JSON → checker 自钉，自钉最后）；
- 连锁 C（preflight 字节变 → `test_rule_cut_evolution_authority_parity.py` 的受保护面 sha）；
- 连锁 D（`PROJECT_LOCK.md` 字节变 → 6+1 继承链，含 antecedent 重算）。

（出处：`docs/research/canonical_batch_20260807/RESEAL_MANIFEST.md`，08-07 批实测。）

所以成本 ≈ **固定的 reseal 底价 × 批次数** + **可变的抄录风险 × 接触的条目数**。这有两个直接后果：

1. **不能一次改一个字段。** 「additive 优先」不等于「碎批优先」——碎批把固定底价乘上批次数。正确形态是**少数几个较大的 additive 批**，每批带机器 diff。
2. **选项的差别不在 pin 数，在抄录风险与可验证性。** 下面三节按这个轴比较。

另有一个独立于 canonical 的低价杠杆，本设计重度依赖它：`rules/canonical_rules.schema.json` **在认证路径的载入时被真正执行**（`load_default_preprocess_context` → `_validate_preprocess_source_schemas` → `jsonschema.validate`，`src/interchange/preprocess_context.py:616-619`）。它是 `rules/` 下的数据文件，**不在 `FROZEN_ARTIFACTS` 里**（已核），改它不触发上面任何一条 pin 链，却能让形态要求在 certified 载入时 fail-closed。这是把 A 组形态需求从「活在文本里」变成「有牙」的最便宜路径，也正面回应 K-2（`semantics` 零消费方 ⇒ 形态要求必须由外部强制）。

代价与配套：schema 一旦成为强制点，它自己必须被钉住，否则强制可以被静默放松。**建议把 `rules/canonical_rules.schema.json` 加入 `FROZEN_ARTIFACTS`**——它不参与派生工件生成，加 pin 的边际成本只有一行常量加一次 sha 更新。（它已登记在 `data/repository_governance/code_assets.json:105`，但那不是哈希 pin。）

### 3.2 选项 (a)：就地增量——条目形态规范化

**改造内容**

- `semantics` 的 13 条目按 §2.1 补字段：`premises[]`、`reachability`、`parameters[]`、`direction`、`scope`、`predicate_status`、`provenance`、`consumers[]`、`id`。
- 分类标签型条目（`mixed_commodity_flow.terminal_clause`、`protocol_storage_box_wireless.slot_count_clause`、`item_admission_port_exclusion`、`machine_min_clearance`）**强制** `parameters[]` 回链 + `reachability`。
- 引理型条目强制 `premises[]`，含约定类前件标注。
- 父句原地改写 + `superseded_readings[]`，废止「父句原文保留、子条款打补丁」形态（现存三处：`terminal_clause` / `slot_count_clause` / `rationale_restated`）。
- 新增 `semantics._entry_contract`（本区形态契约版本号）、`semantics._template`（新增条目的复制源，checker 断言新条目字段集 ⊇ 模板必填集）、`semantics._epoch`（见下）。
- 推导编号表 `#1–#21` 内置进 `semantics._derivation_matrix`，消除 11 个悬空引用。
- schema 侧：`semantics` 从 `additionalProperties: true` 收紧为 `patternProperties` + 逐条目 `required` + `additionalProperties: false`，`_note` / `_epoch` / `_entry_contract` / `_template` / `_derivation_matrix` / `entities` 走白名单。

**`semantics._epoch` 是什么、为什么必须有**：08-07 批向 canonical 加了 22KB 语义内容，`metadata.version` 仍是 `1.2.0`——不是疏忽，是因为 version 会流进派生工件 `current_preprocess_context.json` 的 `source_rules_version` 并被 `src/tests/test_preprocess_context.py:61` 钉住，bump 一次就要连带改派生工件。结果是**canonical 有一大块内容可以变化而没有任何版本信号会动**。这直接卡死 R-28（结论缓存绑规则版本）：绑不到一个永不移动的版本号上。`_epoch` 是一个只在 `semantics` 分区内部、每次语义区变更递增的整数，不流入任何派生工件，因此零派生成本；L2 的前提指纹与所有持久化结论的规则版本戳都绑它。

**迁移路径**（三批，尊重 freeze-ritual）

| 批 | 内容 | 是否动 `statement` 字节 | 机器 diff 断言 | schema 动作 |
|---|---|---|---|---|
| **止血批** | 加 `premises` / `reachability` / `parameters` / `id` / `scope` / `direction`；加 `_epoch` / `_entry_contract` / `_derivation_matrix` | **否**（纯加键） | 旧字段集逐字段 byte-identical（08-07 批已实用过同一手法）；8 个 solver 消费顶层段 byte-identical | 只加「新字段若出现必须合法」，**不设 required**（宽进） |
| **补齐批** | `required` 打开、13/13 齐；`superseded_readings` 改写父句；加 `semantics.entities` 实体镜像；`predicate_status` 全覆盖；`applies_to` 拆三字段 | **是**（父句改写与拆字段） | 逐条目 before/after 结论等价断言由本批的**人工裁决记录**承担，不冒充机器验证；镜像与 L0 的双向等值由 checker 机器断言 | `required` + `additionalProperties: false` 全开；schema 进 `FROZEN_ARTIFACTS` |
| **收敛批** | `provenance` 统一，旧七字段（`adjudicated`/`authority`/`supersedes`/`clarifies`/`source_doc`/`adopted`/`adjudication_ref`）退役 | 否（只搬字段） | 旧字段值 → 新对象的映射表逐项机器比对 | 白名单去掉旧字段名 |

**成本**：三次 reseal 底价（17 pins + 三链 + 全量门 + 慢 lane）。零派生工件重生成（不碰 L0）。补齐批的父句改写是本选项唯一的抄录风险点，且**不可机器验证**——所以它被单独隔离在一批里，并要求逐条目的人工裁决记录，不许混在加字段批里蒙混过关。

**防住**：C-15 / C-14（前件字段化 + 约定类前件标注，写条目时红）、C-17（`reachability` 必填，判据条目不给核算直接红）、C-18 / C-51（`superseded_readings` + 例子/界区分，单读父句不再得到已推翻的结论）、C-10（`direction` 非 `exact` 时必须挂 face 条目、face 条目必须带被排除实例，把「误判过严」的成本前移到登记时）、C-20 / C-28（过严面升格，§4）、C-09 / C-21（`predicate_status` 全覆盖）、C-19 / C-43（前件完整性有位可放）、C-11 / C-12（参数回链 + 实体镜像 `missing[]`）。

**防不住**：
- **填得对不对**。schema 管「字段在场」，管不了「`reachability.verdict` 填的是不是真的」。`NOT_ASSESSED` 与「算错了」在 schema 眼里一样合法。这条只能由消费侧强制（流程轨的重组账 R-15）与外审席补。
- **生成/枚举期过剪**（C-04 / C-47 / C-01）：那是 `placement_generator` 与过滤器的事，不在 canonical 面上。
- **实现侧不跟**（C-08 / C-02 / C-48）：形态管不到代码。`consumers[]` 只提供反向索引的数据基础，真正的传播要靠 L3 的索引 + freeze-ritual checklist。
- **在案裁决失踪**（C-22 / C-30）：需要检索装置，不是形态。
- **触发器永不触发**（C-34）：求解器面；形态只提供 `kind: unreachability` 的登记位。

### 3.3 选项 (b)：派生视图层

**改造内容**：一个生成器 `scripts/gen_rule_views.py`（本批只出规格），从 L0+L1+L2 生成 tracked 视图：

| 视图 | 内容 | 直接对治 |
|---|---|---|
| V1 实体参数表 | 每实体一页：几何 / 口数 / 朝向 / 槽数 / 单槽容量 / 单口速率 / 周期 / 供电 / 放置约束；缺项显式 `MISSING` 并计数 | C-17 C-12 C-05 |
| V2 参数反向索引 | 参数 → 引用它的 L1 条目 / L2 派生条目 / 代码 call site / 持久化缓存 / 外发包 | R-04 R-27；C-49 C-08 C-50 |
| V3 条目-谓词矩阵 | 13 条目 × 6 谓词 + **`axis_without_axiom` 行**（无对应公理的语义轴单列） | C-21——按公理分行的矩阵会系统性丢掉无公理的轴，连通性整轴就是这么消失的 |
| V4 过严/过松面台账 | §4 的登记表投影 + 反向引用 + 哨兵状态 | C-20 C-28 |
| V5 能力覆盖率表 | §5 的能力清单 × 模型可表达性四态计数 | C-06 C-31 |
| V6 派生闭包图 | L2 条目按 level 分层，标 `STALE` / 前提断裂边 | 闭包公理 |

**迁移路径**：不动 canonical 一个字节 ⇒ **零 freeze-ritual**，与 (a) 完全解耦，可先行。canonical 一改 → 生成器重跑 → 视图 diff 进该批 `RESEAL_MANIFEST`。

**必须配 currency 测试，否则等于没做**。仓库里已有这个模式的完整先例，包括它失败的那一半：`scripts/gen_authoritative_numbers.py` + `src/tests/test_authoritative_numbers_currency.py` + 核心节点 `authoritative_numbers.json`。生成器自己的 docstring 记着结论——有 forcing test 的那个数（cut 测试计数）不漂；而「包 README 本应投影这些数字，但注入没接线（`current_claims()` 无消费方）」的那半**照样会漂**。同一个坑在记忆系统侧也踩过（活 hook 消费 `.index` 编译缓存，改卡不 `build-index` 则改动不生效，退役正则因此半月仍活）。所以：**视图必须有 currency 测试，视图的每个数字必须带它的 L0/L1/L2 出处路径。视图是索引，不是替代品。**

**成本**：一个生成器 + 一个 currency 测试 + freeze-ritual checklist 加一步。零 pin 变动（视图 tracked 但不 pin sha）。三个选项里最便宜、最快见效。

**防住**：C-17 的「六个量不在同一页」（V1 把它们放一页并把 `MISSING` 变成可数事实）、C-12、C-49 / C-27 / C-50 的传播面定位（V2）、C-21（V3 的 `axis_without_axiom` 行）、C-31（V5 把「每次对账都落东西」变成可数的覆盖率）。

**防不住**：
- **canonical 里根本没有的东西**。视图变不出单槽容量。所以 (b) 单跑时 V1 会有大片 `MISSING`——这恰是它的第一份价值（把缺口变成清单），但绝不能替代 (a)。
- **不构成卡点**。C-17 的病是「全线推理者消费标签、无人重组参数」；视图让重组变便宜，但没有任何东西强制推理者去看它。卡点在流程轨（R-15 重组账）与 (a) 的 schema 红线。
- **引用视图当证据 = 新一类转述污染**（C-26 同型）。缓解只能靠形态：视图头部写死非权威声明 + 每个数字带出处路径。这个风险是 (b) 引入的净新增风险，须在验收里明确。

### 3.4 选项 (c)：结构重组——否决，但吸收其实体镜像片段

**改造内容（被评估的原案）**：canonical 按实体 / 参数 / 裁决三层重排，散文数字上收进结构化实体条目（最自然的落点是 `facility_templates`），13 条目重写。

**否决论证（四条）**

1. **它要付的是「失去 additive 安全论证」这个代价，不是「多几个 pin」。** 上收到 `facility_templates` ⇒ schema 的 `additionalProperties: false` 必改、`src/rules/models.py:FacilityTemplate` 必改、tracked 派生工件 `current_preprocess_context.json` 字节必变（实测该文件原样嵌入 `facility_templates`）、两个测试连带改。而 08-07 批赖以廉价通过的核心安全论证正是「派生 preprocess 工件八段 byte-identical」——它当场作废，验收从「字节相等」退化为「语义相等」，恰好落进 K-1 点名的抄录风险区。

2. **重写过的散文不可机器验证等价。** K-1 要求重排批带「逐条目 before/after 语义等价断言的机器 diff」。字段级搬迁可以机器比对；`statement` 重写不能——机器只能证明两串字节不同。剩下的验收手段只有人眼逐行，而 C-15 已经证明人眼逐行不收敛（六轮审查逐行审过同一段推理，仍漏一条前件；owner 十秒口算戳破另一条）。用一个已被证伪的验收手段去承接全文最大的一次改动，是把体系最贵的资产押在最弱的一道门上。

3. **它的收益在 (a)+(b) 下可被完全复现。** 「结构化的实体层」= (a) 的 `semantics.entities` 镜像；「按实体重排的可读视图」= (b) 的 V1。重排唯一不可替代的部分是「把散文数字物理搬离 `statement`」，而这一步在 (a) 补齐批里以 `parameters[]` 回链达成——数字仍在原句里，但已经有了机器可解析的回链，读者与 checker 都不再依赖散文。

4. **不可逆。** additive 批出错可以再加一批修正；整体重排出错要靠另一次整体重排回滚，而回滚同样不可机器验证。

**保留的片段**：`semantics.entities` 实体镜像（§2.2）。它吸收了 (c) 的实质收益——一个结构化的实体层，且是**canonical 里唯一能安放「facility_templates 装不下的参数」（单槽容量、冲刷周期、物理口数）的位置**——同时把代价压回 (a) 的加字段量级，因为 `semantics` 是零 solver 消费区。代价是引入了一处重复（镜像 vs `facility_templates`），由双向等值 checker 兜住（§2.2 规则 2）。

**否决的撤销条件**（写明，避免这条否决被当成永久定论）：若将来 solver 真的需要消费实体参数（例如把单槽容量纳入某个认证谓词），镜像就必须上收进 `facility_templates`，届时按「重生成 + 逐字段比对」的重验收方案单独立批。在那之前，重排没有净收益。

### 3.5 对照表

| 轴 | (a) 就地增量 | (b) 派生视图层 | (c) 结构重组 |
|---|---|---|---|
| canonical 字节 | 变（三批） | 不变 | 变（大批） |
| reseal 底价 | ×3 | 0 | ×1 |
| 派生工件重生成 | 无 | 无 | **有**（`current_preprocess_context.json`） |
| schema / pydantic | schema 改，pydantic 不动 | 不动 | **两者都改** |
| 抄录风险 | 低（止血批为零）/ 中（补齐批父句改写） | 零 | **高且不可机器验证** |
| 有牙程度 | 高（schema 在 certified 载入时 fail-closed） | 中（currency 测试） | 高 |
| 能装 canonical 里没有的参数 | **能**（`semantics.entities` + `missing[]`） | 不能 | 能 |
| 见效速度 | 慢（每批一次 freeze-ritual） | **快**（无 freeze-ritual） | 最慢 |
| 可逆性 | 高 | 高 | **低** |

---

## 4. 完整性台账：过严面升格为一等审计面

现状：`semantics.axiom_kernel.model_stricter_faces` 是**一个 JSON 字符串**，散文登记四个面的名字，无参数、无解锁条件、无哨兵、无反向索引（实测，见附录 A）。`failure_taxonomy_and_requirements.md` §2.4 给出它所在层的整体画像：过严 16 : 过松 16 的病例数，对应 2.5 : 16 的防线数，且过严侧病例的发现渠道**全部是人**，零条来自常设装置。

### 4.1 形态

以 `globals.empty_rectangle.emptiness_adjudication` 为结构样板（对象 + `required` + `additionalProperties: false`），升格为双向登记表：

```
"model_faces": {
  "_contract": "每条在册面必须齐备下列字段；缺栏或占位值 = 形态 checker 红",
  "stricter": {
    "MSF-02_source_front_equal_exclusivity": {
      "statement": "模型对 219 台制造机的每个输出口 front 格同样施加外商品实心障碍",
      "implementation_anchors": ["src/models/routing_subproblem.py:1233",
                                 "src/models/routing_subproblem.py:1244-1246",
                                 "src/models/routing_subproblem.py:1271",
                                 "src/models/routing_subproblem.py:1282"],
      "why_stricter": {
        "argument_ref": "derivation:#8",
        "covers": "输入口（污染链：机器口无内容选择权，混流必吞错货）",
        "does_not_cover": "输出口（只往外推货，无吞错货机制）"
      },
      "excluded_game_legal_instance": {
        "kind": "instance | estimate | none",
        "witness": "…具体布局或具体 pose…",
        "measured": "…"
      },
      "rejection_risk": {
        "could_cut_optimum": "yes | no | unknown",
        "argument": "…",
        "probe": "src/tests/…::probe_…"
      },
      "unlock_path": {"blocking": [...], "batch": "…", "owner_gate": true},
      "acceptable_because": "…当前接受的理由，须为一句可被反驳的断言…",
      "registered_by": "…", "registered_on": "2026-08-06",
      "consumers": ["docs/…#§3", "derived:D-…"],
      "sentinel": "src/tests/…::test_…"
    }
  },
  "looser": { … 同构，装已知过松/待收紧面 … },
  "candidates": { … 拒真席提交、未经 owner 裁决的候选面 … }
}
```

四条形态规则：

1. **`excluded_game_legal_instance.kind = "none"` 的条目不能进 `stricter`，只能待在 `candidates`。** 这是 K-6 的形态化：没有「游戏合法但被模型拒」的具体实例，该面就没有被证明过严。C-10（把正确的保守编码误判为保真缺口，整份分析一天内作废）是这条规则存在的理由。
2. **`rejection_risk.could_cut_optimum` 无默认值，`unknown` 合法但会被计数**，且计数进入 §5 的覆盖率账与每条承重结论的方向暴露栏（R-33）。「我们不知道这个面是否砍掉了最优解」是可接受的状态，「我们没问过」不是。
3. **`consumers[]` 必须真实**：任何文书或 L2 条目若把某个面当论证支点，必须在该面条目里登记反向引用。改动或放开该面时，形态 checker 断言 `consumers` 全部已被重判——这是 C-28 那次「放开押在待放开的面上、两处改动分属不同批互不引用」的机器化封堵。
4. **`sentinel` 必填**：每个在册面挂一个哨兵测试，且哨兵必须满足既有质量线——选「除该守卫外全链路合法」的几何（否则被别的机制挡死，测不出承重），验收输入必须是被验链自产字节，探针必须物理可实现。

### 4.2 新增过严面的登记义务落在谁头上

四条义务，按「谁最先知道」分配，不按「谁最有空」分配：

| 角色 | 义务 | 触发时机 | 不履行的后果 |
|---|---|---|---|
| **实现改动者** | 任何使模型更严的改动（新增守卫 / 收紧剪枝 / 新增 fail-closed 回退）必须登记一个 `stricter` 面，或在批次记录里显式声明「本批不新增过严面」 | 改动合入前 | 形态 checker 的 `direction` 对账发现无主的更严面 ⇒ 门红 |
| **论证作者（承重文书）** | 若某步论证的支点是「模型碰巧更严」，必须在**那条面的条目里**登记反向引用（`consumers`），不能只在自己的文书里提一句 | 文书入库/外发前 | 席位清单卡点拦下 |
| **拒真席（§5、R-16）** | 发现候选过严面 → 提交到 `candidates`，**带一个游戏合法但被模型拒的实例**；无权自行升格为 `stricter`，更无放开授权 | 每次承重文书评审 | 无实例的候选不入册 |
| **owner** | `candidates` → `stricter` 的裁决、`unlock_path` 的放行 | 裁决包到桌 | — |

**兜底**：freeze-ritual checklist 新增一步「本批是否新增/改变了过严面或过松面？」，全否也留痕（与过堂表全「不适用」也留痕同规格）。

**明确不该由谁负责**：不能把登记义务放在审查席身上。审查席是**发现者**，不是登记者。C-20 的现状就是这个错位的产物——外审席发现了 source-front 过严面并登记了名字，但「被排除能力有多大」的估计没人补，因为发现者交完就走了，而实现侧没有接收义务。

---

## 5. 能力盘点对账（墙审计）

守卫审计问的是「模型放进来的解，游戏里合法吗」（**孔审计**，找纳伪）。它的对偶是「游戏里合法的能力，模型表达得出吗」（**墙审计**，找拒真）。今天只有前者有装置。

### 5.1 能力清单是一等累积资产

载体：`rules/derived/capability_register.json`（L2 侧，tracked，不进 `FROZEN_ARTIFACTS`）。它是**收件箱兼台账**：新能力先在这里登记，经 owner 裁决后其规则形态以 additive 方式晋级进 L1，register 条目标 `PROMOTED` 并指向 L1 路径。

放在 L2 而不是 canonical 的理由与 §1.2 同：新器件、新能力的发现是持续的（C-06 的物品/管道准入口整类器件是 owner 08-05 主动供出的，此前从未提过），每发现一条就付一次 freeze-ritual 底价 ⇒ 没人会去盘点。

条目形态：

```
{
  "id": "CAP-037",
  "statement": "限制口可对单一 itemId 设 perMinuteLimit，未放行的货留在上游而非被丢弃",
  "source": {"kind": "simulator_registry | axiom | owner_ruling",
             "ref": "IndustrialPlanner@8da9017a::admissionRule"},
  "model_expressibility": "expressible | expressible_but_unused | not_expressible | out_of_scope",
  "evidence": {"kind": "constructive_witness | encoding_pointer | probe | argument",
               "ref": "…"},
  "if_not_expressible": {"excluded_solution_class": "…",
                         "impact_on_bounds": "…",
                         "linked_face": "MSF-xx"},
  "scope": "certified | p2_0_flow | narrative",
  "last_verified": "2026-08-07", "verified_by": "…"
}
```

### 5.2 枚举从哪里来（有界，可枚举，不是「查所有能力」）

三个源，各自的枚举都是有限的：

1. **模拟器规则层**：上游 IndustrialPlanner 注册表的「器件类型 × 该器件声明的 rule 字段」。这是一张有限表，可脚本抽取。C-06 的准入口参数（1×1、直通不可弯、`admissionRule={itemId, limit, perMinuteLimit}`）就来自这里。
2. **公理系**：A1–A11 每条公理蕴含的动作（运输 / 转化 / 准入 / 供电 / 商品身份…），逐条展开为「这条公理允许做什么」。有限，且展开一次即固定。
3. **owner 裁决库**：`OWN-M*` 编号的历次实测定谳。有限且已编号。

这满足 K-4 的有界性要求。**能力清单是累积资产**——直接补上 V-4 的漏洞（「模拟器对账的判例集不是累积资产，每次对账重写判例，跑过的判例没有回归位」）：CAP 条目连同它的探针一起沉淀，下次对账是增量而非重来。

### 5.3 可表达性怎么核

- `expressible`：给**构造性证据**——一个最小实例，模型接受它。不接受论证代替实例。
- `not_expressible`：给**机器证据**——模型在该实例上返回 INFEASIBLE，或该实例不在候选池（可用 `candidate_placements` 直接查）。同样不接受论证。
- 探针的忠实性判据必须编进探针自身（fail-closed），不能只写在文档里。C-39 是活样本：`open_yard` 探针的口朝向把机身放进了空场，装置在真实几何里不可能存在，于是产出假红利；忠实变体的真实结果是 TIMEOUT。自产字节能管住「链没被绕过」，管不住「输入本身不可能存在」。
- `unknown` 不是一个可表达性取值——没核过就是 `not_verified`，且进计数。

### 5.4 覆盖率账与它的消费点

V5 视图输出四个数：`total / expressible / not_expressible / not_verified`。

**消费点（否则又是一张便签）**：任何声称全局最优性的承重结论，其方向暴露栏（R-33）必须写明「本结论依赖的过严面清单」与「本结论作出时 `not_verified` 的能力数」。`not_verified > 0` 不阻断出结论，但阻断把该结论叙述为「无条件」。这把 C-31（owner 定性的「每次对账都会落下东西」）从一种感觉变成一个随结论一起发布的数字。

---

## 6. 推荐组合与迁移排期

**推荐组合：(b) 先行 → (a) 三批 → (c) 只吸收实体镜像片段（并入 (a) 补齐批）→ L2 派生层与 §4/§5 随 (a) 补齐批与收敛批落地。**

一句话理由：reseal 底价让「改 canonical」注定是低频动作，所以先做零 canonical 成本的视图层把缺口变成可数清单，再用少数几个 additive 批一次性补进去——而不是发现一条补一条。

| 阶段 | 动作 | 动 canonical | 主要产出 | 卡点接线 |
|---|---|---|---|---|
| **S1 视图先行** | `gen_rule_views.py` + currency 测试 + V1/V2/V3 三张视图 | 否 | 实体参数表（含 `MISSING` 计数）、参数反向索引、条目-谓词矩阵 | freeze-ritual checklist 加「重跑生成器 + 视图 diff 进 RESEAL_MANIFEST」 |
| **S2 派生层立架** | `rules/derived/derived_rules.json` + schema + currency 测试（前提指纹重算）；把两个样板案例（§7）作为首两条 L2 条目录入 | 否 | 派生闭包台账可用；闭包扫描有落点 | 承重文书席位清单加「新推出的规则须落 L2 条目」 |
| **S3 止血批** | (a) 止血批：纯加键，`premises` / `reachability` / `parameters` / `_epoch` / `_derivation_matrix`；schema 宽进 | **是** | C-17 / C-15 两型在写条目时可被红 | schema 进 `FROZEN_ARTIFACTS`；新增形态 checker（advisory） |
| **S4 补齐批** | (a) 补齐批：`required` 全开、父句原地改写、`semantics.entities` 实体镜像、`predicate_status` 全覆盖、`applies_to` 拆三字段、`model_faces` 双向登记表（§4） | **是** | 形态契约完整；过严面成为一等审计面 | 形态 checker 转硬门（owner 决策）；拒真席进席位清单 |
| **S5 能力盘点** | `capability_register.json` + 三源枚举 + V5 覆盖率表 | 否 | 墙审计有装置；覆盖率进方向暴露栏 | 证书发布 checklist 加「本结论依赖的过严面 + `not_verified` 数」 |
| **S6 收敛批** | (a) 收敛批：`provenance` 统一，旧七字段退役 | **是** | 裁决元数据单一形态 | — |

**S1/S2/S5 与 S3/S4/S6 可并行**：前者不动 canonical，不占 freeze-ritual 窗口。

**三次 canonical 批（S3/S4/S6）应尽量与其他线的 canonical 需求合批**——同目录 `failure_taxonomy_and_requirements.md` §5 已列出至少两笔挂账的 canonical 措辞修改（C-15 的 REJUDGE 措辞 diff、C-17 的箱条款措辞），它们与 S3 天然同批：底价付一次。

---

## 7. 两个样板案例在新形态下的走向

这一节是形态设计的验收：新形态若拦不住已经发生过的那两件事，它就没通过。

### 7.1 负例——协议箱堵塞判据不可达（C-17）

| 环节 | 新形态下发生什么 |
|---|---|
| 写实体条目 | `semantics.entities.protocol_storage_box` 的 `buffer.slot_capacity` 是必填键。作者手上没有这个数 ⇒ 只能写进 `missing[]`。**「我们不知道箱的单槽容量」从一个无人察觉的空白变成一条被计数的事实**（V1 的 `MISSING` 计数）。今天它连空白都算不上——最接近的邻居是制造机的 `one input buffer slot × 50`，极易被误取。 |
| 写判据条目 | `slot_count_clause` 的 statement 含「blocks exactly when」⇒ schema 强制 `reachability`。作者必须列出 `parameters[]`——列出的那一刻，`3 口 × 1 件/tick ÷ 2.0 s × 10 s = 15` 与 `6 × 50 = 300` 落在同一个数组里，这是一行算术。 |
| 作者偷懒 | 写 `verdict: NOT_ASSESSED`。形态 checker 检查该条目 `scope: certified` 且 `direction: stricter` ⇒ **禁止 `NOT_ASSESSED`，红**。 |
| 闭包扫描独立命中 | `free_variable: box_occupied_slots ∈ [0, 6]`；两条 L0 参数（到货速率、冲刷周期）与一条容量参数联立 ⇒ 危险事件的可行集为空 ⇒ 结晶检测器 `capacity_vs_arrival` 触发 ⇒ 自动开一条 L2 条目 `kind: unreachability`，level 1。**这一步不依赖任何人想起要去验算**——这正是三周无人做这步验算的那个空档。 |
| 标签的下游消费 | `mixed_commodity_flow.terminal_clause` 的 class(2) 标签 `direction: stricter` ⇒ 必须挂 `face_ref` ⇒ 该面条目必须给 `excluded_game_legal_instance`（= 以箱为终点的汇流区布局）⇒ 无实例则只能待在 `candidates`，而 `candidates` 里的面**不能被下游当既定前提消费**。 |

新形态在**四个独立位置**上挡住同一条病（实体条目的 `missing`、判据条目的 `reachability`、闭包扫描的结晶检测、标签的 face 登记），且其中一个（闭包扫描）不需要任何人事先怀疑。

### 7.2 正例——「5 满 1 半」条件定理

owner 直觉命中的结晶案例：6 台制瓶机总占空 11/2，在带容量 1 件/tick、配方 2:1、免分流目标约束、六台全开这四层前提下，每台占空的连续自由度塌成两档 `{1/2, 1}`，总量把档位分布定死为 k=5 满 1 半，结晶出可直接查布局的结构特征——「免分流布局中恰一台制瓶机只用一个进料口」。

（推导本体归 P2.0 线复核；本节只用它检验形态承载。相关的占空自由度事实已在 `docs/research/p2_0_specialized_20260807/refute_round1/REJUDGE_REPORT.md` 立案：同一 operation 的台间占空不是均摊，而是 42 维自由度；「6 台各 11/12」与「5 台满速 + 1 台半速」都合法。）

它在新形态下的完整落点：

- **前提集**分属四个来源，各有 `kind`：`belt_capacity_per_tick`（`parameter`，L0）、配方 2:1（`parameter`，L0）、六台全开与 `x_op = 11/2`（`derived`，L1 或更低层 L2）、免分流（`assumption`，`not_dischargeable_in: ["certified"]`）。**最后一条是关键**：它把这条定理牢牢按在 `scope: p2_0_flow`，永远不会被误引进认证链（K-7 的机器化）。
- **结晶块**：`free_variable = duty[bottling_op] ∈ [0,1]^6, Σ = 11/2`，`collapsed_to = d_i ∈ {1/2, 1}，恰一个取 1/2`，`detector = integrality_argument`。
- **层级**：`level = 1 + max(前提层级)`，自动算出。
- **立即可用于下一级**：`kind: structural_feature` 的条目，其 statement 是可直接对布局求值的谓词 ⇒ 它进入下一轮扫描的前提池，与几何类规则组合出下一级（例如与「制瓶机进料口朝向」「机身间距」组合，压缩免分流布局的位姿空间）。
- **自动失效**：若将来某条前提变了（产量目标改、带容量改、免分流目标被放弃），`premise_fingerprint` 现场重算不符 ⇒ currency 测试红 ⇒ 条目转 `STALE`，所有引用它的下游条目按 `consumers[]` 被逐条重判。今天这类定理散在批次文书里，前提一变没有任何东西会红。

---

## 8. 覆盖对照

### 8.1 对 A 组形态需求（R-01…R-14）

| 需求 | 由谁承担 | 落点 |
|---|---|---|
| R-01 前件字段化 | (a) | `premises[]`，含 `kind: convention` |
| R-02 前件可 discharge 性 | (a) | `dischargeable_in` / `not_dischargeable_in`；L2 `scope` 校验 |
| R-03 判据带可达性核算 | (a) | `reachability`，certified+stricter 禁 `NOT_ASSESSED` |
| R-04 参数机器可解析 + 反向索引 | (a)+(b) | `parameters[]` + V2 |
| R-05 单实体参数表 | (a) 的实体镜像 + (b) 的 V1 | `semantics.entities` 含 `missing[]` |
| R-06 方向标注 + 双向登记 | (a) | `direction` + `model_faces.{stricter,looser,candidates}` |
| R-07 过严面带参数 | (a) | §4 形态 |
| R-08 废止打补丁子条款 | (a) 补齐批 | `superseded_readings[]` + checker |
| R-09 裁决元数据统一 | (a) 收敛批 | `provenance` |
| R-10 `predicate_status` 全覆盖 | (a) 补齐批 | 必填 + `applies_to` 拆三字段 |
| R-11 derivation 编号表内置 | (a) 止血批 | `semantics._derivation_matrix` |
| R-12 `semantics` 纳入 schema | (a)，三批递进 | 宽进 → `required` → 白名单收敛 |
| R-13 例子 vs 界 | (a) | `superseded_readings` + statement 内 `example` 标注 |
| R-14 结论语义作用域 | (a) | `scope` |

### 8.2 对 B 组流程需求的形态侧承载

流程需求归推理流程轨；形态轨只负责提供它们需要的位。

| 需求 | 形态侧提供什么 | 形态侧不做什么 |
|---|---|---|
| R-15 消费侧重组账 | 条目自带 `reachability`，重组账可引用而非重算 | 不强制推理者去看——卡点在文书模板 |
| R-16 拒真席常设 | `model_faces.candidates` 是它的收件箱；`excluded_game_legal_instance` 是它的输出规格 | 不设席位、不定通道 |
| R-17 过严面挂估计与探针 | `rejection_risk` + `sentinel` 字段 | 不跑探针 |
| R-18 剪枝 exclusion 审计 | `direction` 与 face 登记可容纳剪枝规则 | 剪枝在生成器侧，形态管不到 |
| R-19 fail-closed 计数 | `looser`/`stricter` 面可登记塌陷面 | 计数器在被测码里 |
| R-20 可达性两问 | `reachability.verdict` 与 L2 的 `kind: unreachability` | 两问进过堂表是流程轨 |
| R-23 跨批耦合登记 | `consumers[]` 双向 + checker 断言 | 检索纪律是流程 |
| R-27 变更传播机器化 | V2 反向索引 + L2 前提指纹 | 三态账的裁定是人 |
| R-28 结论缓存绑规则版本 | `semantics._epoch` + `premise_fingerprint` | 求解侧接线不在本设计 |
| R-33 方向暴露标注 | `direction` + face 清单 + 能力覆盖率四数 | 证书台账结构是流程轨 |

### 8.3 本设计明确挡不住的

按病例列出，避免被读成万能：

- **C-04 / C-47 / C-01 生成期过剪**：在 `placement_generator` 与过滤器侧，canonical 形态触不到。形态只能提供 face 登记位。
- **C-08 / C-02 / C-48 实现侧不跟**：`semantics` 零消费方是这条的结构成因，本设计不改这一点（改了就要动 solver 消费面，代价见 §3.4）。缓解手段是 V2 反向索引把 call site 列出来，但「列出来」不等于「改了」。
- **C-34 触发器永不触发**：求解器面。形态提供 `kind: unreachability` 登记位与闭包扫描的检测器，但 cut 触发条件的可达性要在求解侧实测。
- **C-22 / C-30 在案裁决失踪**：需要检索装置（开工检索前置 R-24）。形态提供 `consumers[]` 与 L2 闭包图作为检索的数据基础。
- **「字段填得对不对」**：schema 与 checker 管在场与一致性，管不了正确性。这一格永远需要外审席。
- **(b) 引入的净新增风险**：视图被当权威引用（C-26 同型）。缓解靠视图头部声明 + 每数字带出处路径，不是消除。

---

## 9. 交回的答复与未决问题

`failure_taxonomy_and_requirements.md` §5 把三个问题点名给设计席，答复如下。

**§5-1 分批策略：additive 三批，止血批可做到纯加键。** C-17 与 C-15 的止血（加 `reachability` / `premises`）**不需要动任何 `statement` 字节**，因此可以走 08-07 批同款的「旧字段逐字段 byte-identical」机器 diff。父句改写（R-08）与 `applies_to` 拆字段是唯一需要动原文的动作，被单独隔离进补齐批，并要求逐条目人工裁决记录——不冒充机器验证。整体重排否决，论证见 §3.4。

**§5-2 checker 的强制点：优先用 schema，schema 表达不了的再落新结构 checker。**
- `rules/canonical_rules.schema.json` 在认证路径载入时被真正执行（`src/interchange/preprocess_context.py:616-619`），且是 `rules/` 下的数据文件、不在 `FROZEN_ARTIFACTS` 里——改它零 pin 链、却能 fail-closed。字段在场性、枚举值、类型、`additionalProperties: false` 全部走这里。
- schema 表达不了的三类落新 checker `scripts/check_canonical_rule_form.py`（与 `check_p1_2_proof_obligations.py` 同族）：①实体镜像与 `facility_templates` 的双向等值；②`reachability` 在 certified+stricter 条目上禁 `NOT_ASSESSED`；③`consumers[]` 与 L2 `premises[]` 的双向引用一致性。
- **建议该 checker 不纳入 close-kernel V99 自钉链**：它审的是 descriptive 区，不是 proof-bearing sink；纳入会给每次形态调整都挂上 checker 自钉的连锁。
- **建议先进 preflight 的 advisory 段，跑满一个批次周期后再转硬门**（避免一上来把全量门锁死在一个刚上线的形态契约上）。转硬门是 owner 决策。
- **配套硬要求**：schema 成为强制点后必须进 `FROZEN_ARTIFACTS`，否则强制可被静默放松。

**§5-4 反向索引的产出形式：可重建 cache + currency 测试，不进 hash。**
- 进 hash 的后果：改一个参数 → 索引重生成 → canonical（或另一个冻结件）sha 变 → 17 pins + 三链。索引会变成 freeze-ritual 的放大器，而它每天都在变。
- 老坑（「活 hook 消费编译缓存，忘了重建就不生效」）用 **currency 测试**堵，不用纪律堵。仓库自己的先例已经把这两条路的结果都跑出来了：`authoritative_numbers` 有 forcing test 的那个数不漂，没接线的那半照样漂。

**留给 owner 的三项裁决**

1. **形态 checker 是否进 CI 硬门、何时进。** 本席建议：S3 上线为 advisory，S4 完成后转硬门。
2. **`rules/canonical_rules.schema.json` 是否加入 `FROZEN_ARTIFACTS`。** 本席建议：加，与 S3 同批。这是把形态契约从「可被静默放松」变成「改它要走 ritual」的唯一手段，边际成本一行常量。
3. **`rules/derived/` 这个非冻结的规则目录是否可接受。** 它与「`rules/` 下全是冻结件」的现有直觉冲突。本席建议接受，并在 `rules/derived/README.md` 头部写死非冻结状态与引用纪律；备选落点 `data/rule_closure/`。

**留给推理流程轨的接口**（本设计假定对方会接，若不接则以下形态位是空的）：R-15 重组账的文书模板栏位、R-16 拒真席的席位与通道、R-20 两问进过堂表、R-21 审查覆盖层声明、R-29 owner 裁决包必带「裁决为 A / 为 B 各自扔掉什么解空间」、饱和扫描的运行纪律与验收。

---

## 附录 A：本文依据的仓库事实（现场机器核实，2026-08-07）

| # | 事实 | 核实方式 |
|---|---|---|
| A1 | `semantics` 在 schema 里只有 `{type: object, description, additionalProperties: true}`——无 `required`、无字段枚举、无子结构 | `python -c "json.load(open('rules/canonical_rules.schema.json'))['properties']['semantics']"` |
| A2 | `semantics` 区共 `_note` + 13 个条目 | 同上，对 `canonical_rules.json` |
| A3 | `model_stricter_faces` 与 `ruling_level_inputs` **都是普通 JSON 字符串**（散文），非结构化对象 | 同上；**订正 `canonical_anatomy.md` §5 关于 `ruling_level_inputs` 形态的表述** |
| A4 | 全文真正结构化的裁决样板是 `globals.empty_rectangle.emptiness_adjudication`：`required: [decided_on, authority, source_doc, statement]` + `additionalProperties: false` | schema dump |
| A5 | `facility_templates` schema：`patternProperties` + `required: [dimensions, rotatable, needs_power, is_solid_z, port_rule]` + `additionalProperties: false`；pydantic 侧 `FacilityTemplate(StrictBaseModel)`，`src/rules/models.py:119-129` | schema dump + `rg` |
| A6 | `protocol_storage_box` 模板只有 `dimensions/rotatable/needs_power/is_solid_z/port_rule` 五个键——无槽数、无容量、无口数、无周期 | canonical dump |
| A7 | `preprocess_context` 把 `facility_templates` deepcopy 进上下文（`:230`），并原样落进 tracked 派生工件 `data/solutions/current_preprocess_context.json`（实测该文件的 `protocol_storage_box` 条目与 canonical 同形） | `rg` + `python -c` 对比 |
| A8 | canonical schema 在认证路径载入时被 `jsonschema` 真正执行：`load_default_preprocess_context` → `_validate_preprocess_source_schemas`（`src/interchange/preprocess_context.py:611-624`） | 源码逐行 |
| A9 | `rules/canonical_rules.schema.json` **不在** `FROZEN_ARTIFACTS`（该表 4 项：canonical / preprocess_plan / mandatory_exact_instances / generic_io_requirements）；它登记在 `data/repository_governance/code_assets.json:105`，但那不是哈希 pin | `scripts/preflight_gate.py:62-69` + `rg` |
| A10 | canonical sha 的直接 pin 面 17 处（代码/测试 4 + 文档 13）+ 连锁 B/C/D；08-07 批实测 | `docs/research/canonical_batch_20260807/RESEAL_MANIFEST.md` §1-2 |
| A11 | 08-07 批为纯 additive，因此 schema / pydantic / 派生 preprocess 工件全部未动，安全论证是「八段 byte-identical」 | 同上 §2「不需要动的面」+ `DEPENDENCY_VERIFICATION.md` |
| A12 | `metadata.version` 保持 `1.2.0` 未 bump——因为它流入 `current_preprocess_context.json` 的 `source_rules_version` 并被 `src/tests/test_preprocess_context.py:61` 钉住 | RESEAL_MANIFEST §0 + 测试源码 |
| A13 | 「生成器 + 核心节点 + currency 测试」在仓库里已有可用先例，且其未接线的那半确实漂了：`scripts/gen_authoritative_numbers.py` 与 `src/tests/test_authoritative_numbers_currency.py`（后者 docstring 自述包 README 的投影未接线、仍会漂） | 两文件 docstring |
| A14 | 推导编号表 `#1–#21` 在 `docs/research/canonical_batch_20260807/AXIOM_KERNEL_PROPOSAL_20260806.md:131`，不在冻结件内 | `rg` |
| A15 | 占空自由度事实（同一 operation 台间占空非均摊、42 维、「5 台满速 + 1 台半速」合法）已在案 | `docs/research/p2_0_specialized_20260807/refute_round1/REJUDGE_REPORT.md:17,34,52` |

---

*本文件只写本路径下的设计规格。未修改 `rules/canonical_rules.json`、`rules/canonical_rules.schema.json`、任何 `src/`、`scripts/` 或锁面文件，未跑 git 提交。*
