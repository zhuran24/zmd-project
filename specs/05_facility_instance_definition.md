---
status: CURRENT_CODE_ALIGNED
source_of_truth: instance roster = src/preprocess/instance_builder.py + frozen artifacts; port/provider semantics = rules/canonical_rules.json + rules/preprocess_plan.json
last_verified_against: 2026-07-18 owner 端口语义裁决与 Batch 3+5 provider-map 实现
owner: preprocess-instances
---
# 05 设施实例化与全局刚体花名册 (Facility Instance Definition)

## 5.1 文档目的与当前边界

本章记录当前项目里“实例花名册”到底分成哪几类，以及哪些工件能进入 `certified_exact` 主线。

当前仓库的实例工件已经明确分层：

1. `mandatory_exact_instances.json`
   - **严格精确主线可读**
   - 只包含 certified exact 所需的刚体实例
2. `exploratory_optional_caps.json`
   - **仅 exploratory 可读**
   - 记录经验上限，不是 exact-mode 证明边界
3. `all_facility_instances.json`
   - **exploratory / compatibility 支持工件**
   - 是方便 viewer、兼容层和探索路径使用的全集，不是 certified exact 的正式实例真源

因此，当前 certified path 在实例层的直接真源是：

- `data/preprocessed/mandatory_exact_instances.json`
- `data/preprocessed/generic_io_requirements.json`

而不是 `all_facility_instances.json`。Generic-input provider 容量另由同一 certified artifact 快照中的
`rules/preprocess_plan.json` 整张 operation map 给出。

---

## 5.2 制造单位实例化 (Manufacturing Instances)

根据当前冻结 preprocess 工件，需要实例化 **219 台制造机器**。

- **实例化总量**：219 台
- **命名规范**：`<operation_type>_<三位流水号>`
- **求解约束**：**强制必选（Mandatory / exact）**
- **来源**：`machine_counts.json` + `src/preprocess/instance_builder.py`
- **模板映射来源**：当前由 `PreprocessContext` 驱动生成的 `TEMPLATE_MAPPING`，不再手写 17 条 recipe -> template 常量表

这些制造实例进入 `mandatory_exact_instances.json`，并且是 certified exact 主模型必须放置的实体。

---

## 5.3 核心与边界接口实例化 (Core & Boundary Instances)

### 5.3.1 协议核心 (Protocol Core)

- **实例化数量**：严格为 **1 座**
- **实例 ID**：`protocol_core_001`
- **求解约束**：**强制必选（Mandatory / exact）**
- **角色**：协议核心自带 14 个实体通用输入口与 6 个实体通用输出口；前者是 mandatory provider 容量，后者并入全局资源来源池

### 5.3.2 边界原生仓库口 (Boundary Storage Ports)

- **实例化数量**：严格为 **46 个**
- **实例 ID**：`boundary_port_001` ~ `boundary_port_046`
- **求解约束**：**强制必选（Mandatory / exact）**
- **角色**：贴左/下边界放置，承担原矿进入工厂的物理入口职责

这两类实体与 219 台制造实例一起构成 certified exact 主线读取的强制刚体集合：

- 219 台制造实例
- 1 个 protocol core
- 46 个 boundary ports

合计 **266 个 exact mandatory instances**。

---

## 5.4 Exploratory Optional Caps（探索模式经验上限）

当前仓库仍保留两类 exploratory optional 设施：

### 5.4.1 供电桩 (Power Poles)

- `facility_type = power_pole`
- `operation_type = power_supply`
- exploratory cap = **50**

### 5.4.2 协议储存箱 (Protocol Storage Boxes)

- `facility_type = protocol_storage_box`
- `operation_type = box_sink`
- exploratory cap = **10**

这些上限只记录在：

- `data/preprocessed/exploratory_optional_caps.json`
- `data/preprocessed/all_facility_instances.json`

它们的含义是：

> **探索模式候选池上界**，而不是 certified exact 的硬约束。

如果文档里出现 `50 / 10`，应默认把它理解为 exploratory guidance，而不是 exact 主线事实。

### 5.4.3 Certified exact 中的实体 provider 与端到端路由语义

`rules/canonical_rules.json` 声明 `protocol_storage_box.port_rule = "opposite_parallel_sides"`；协议箱与 `manufacturing_3x3` 使用同一实体口几何：一侧 3 个输入口、对侧 3 个输出口、四种正交端口模式，并且需要供电。`rules/preprocess_plan.json` 的 `box_sink.generic_input_slots = 3` 必须与选中 pose 的 3 个 `input_port_cells` 严格相等。协议箱输出口真实存在，但在当前生产线中允许不连接；未激活的口不占用 front cell。“无线”只描述协议箱把缓存送入仓库的箱后段，不提供生产设施到协议箱的无线拾取。

协议核心同样是 generic-input provider：`protocol_core.generic_input_slots = 14`，每个选中 pose 同时具有 14 个实体输入口与 6 个实体输出口。Binding 将每个正数 `required_generic_inputs` 商品精确分配到某个 provider 的具体实体输入口；未用容量可取 `__unused__`。已分配输入口由 `extract_port_specs()` 导出为 routing sink，商品生产设施的输出口仍导出为 routing source。因此这些成品必须从生产端到协议箱或核心输入口**端到端 routed**，front 可用性与 routing 连通性都属于 certified gate。

Generic **output** 槽继续采用精确计数语义（F-BIND-R1-01）：每个可见输出槽的 domain = 真实外部源商品集 ∪ `__unused__`，槽内 ExactlyOne；真实商品全局出现次数 `sum == demand`。当前基地 52 需求 = 52 槽时哨兵被逼为 0；需求较小时多余槽可空置。`__unused__` 是 binding 保留名，不能出现在需求工件中，也不会生成 port spec。

Generic I/O 与 provider map 都使用 fail-closed strict JSON：双需求 section 必须存在，计数必须是严格非负整数，重复 key 与 `NaN`/`Infinity` 一律拒绝。Certified session 对 `canonical_rules`、`generic_io_requirements` 与 `preprocess_plan` 执行**单读取、单解析、单快照**；从已哈希的 plan 字节解析完整 `generic_input_slots_by_operation`，并把整张 map 原子传给 master、outer safe-area、campaign proof helper、coordinate/pose 统计与 binding。Outer/session 比较整张 map，禁止退化为 `box_sink` 单值或在 binding 阶段二次读盘。

协议箱 required-optional 下界是 provider-aware 且 instance-aware：先按 `box_sink` 每箱 3 槽计算 gross demand，再扣除真实 mandatory exact provider 实例的 operation 容量。当前 mandatory `protocol_core_001` 可提供 14 槽；仅在 rules 中存在核心模板不能获得抵扣。Mandatory 协议箱及未来 provider 也按同一规则计入，剩余需求再向上取整为协议箱数。

> [!NOTE]
> **Superseded historical reading（2026-07-18 前）**：旧文档曾把协议箱描述成 `omni_wireless`、`wireless_sink` 和无坐标的虚拟槽，并据此把 generic-input 成品视为 routing-free。Owner 实测与当前 canonical semantics 已明确废止该解释；这些术语只可出现在带有 historical/superseded 标记的证据中，不能进入现役求解契约。

---

## 5.5 当前实例工件的正确阅读方式

### Certified exact 主线

只应读取：

- `mandatory_exact_instances.json`
- `generic_io_requirements.json`
- 同一 frozen snapshot 中的 `rules/preprocess_plan.json`（完整 provider capacity map）

### Exploratory / compatibility / viewer 支持层

可以读取：

- `all_facility_instances.json`
- `exploratory_optional_caps.json`

但这些工件不能反向定义 certified exact 的实例语义。

---

## 5.6 当前仓库中的数量关系

当前冻结工件对应的数量关系为：

- `mandatory_exact_instances.json`：**266** 条
- `all_facility_instances.json`：**326** 条
  - 其中 266 条是 exact mandatory
  - 其余 60 条来自 exploratory optional caps

因此，`326` 这个数字只能表示：

> “探索兼容全集的规模”

而不能表示：

> “certified exact 主线统一读取的实例身份证池”

---

## 5.7 与 preprocess context 重构的关系

当前项目已经新增 `rules/preprocess_plan.json` 与 `src/interchange/preprocess_context.py`，用于把 recipe / template / cycle / utility truth 从 Python 硬编码迁移到 build-time context。

这次重构改变的是：

- 制造实例如何从数据上下文再生
- `TEMPLATE_MAPPING` 如何生成

它**没有**把 `PreprocessContext` 本身提升为 certified runtime authority：

- certified runtime 仍读取冻结的 `mandatory_exact_instances.json` 与 `generic_io_requirements.json`
- provider capacity 从同一已哈希快照的 `rules/preprocess_plan.json` 解析
- `PreprocessContext` 仍只是 preprocess 再生层的 build-time contract
