---
status: CURRENT_CODE_ALIGNED
source_of_truth: src/preprocess/instance_builder.py and frozen preprocessed instance artifacts
last_verified_against: 2026-03-25
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

而不是 `all_facility_instances.json`。

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
- **角色**：协议核心自带 6 个通用输出槽，并入全局资源来源池

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
- `operation_type = wireless_sink`
- exploratory cap = **10**

这些上限只记录在：

- `data/preprocessed/exploratory_optional_caps.json`
- `data/preprocessed/all_facility_instances.json`

它们的含义是：

> **探索模式候选池上界**，而不是 certified exact 的硬约束。

如果文档里出现 `50 / 10`，应默认把它理解为 exploratory guidance，而不是 exact 主线事实。

### 5.4.3 Certified exact 中的协议箱无线消费语义

`rules/canonical_rules.json` 声明 `protocol_storage_box.port_rule = "omni_wireless"`，`rules/preprocess_plan.json` 声明 `wireless_sink.generic_input_slots = 3`。因此 certified exact 中的协议箱不是带实体端口的 3×3 机器，而是由需求驱动激活的 required-optional wireless sink。

被选中的协议箱 pose 必须只暴露 3 个虚拟 generic input 槽：槽参与 binding 的 commodity 分配与 `__unused__` 互斥数学，但不携带坐标、方向或 port cell，也不经过 routing front 可用性过滤。`extract_port_specs()` 不得为这些虚拟槽输出 port spec，因此 routing 与 flow 子问题不会收到通向协议箱的 sink front；无线消费只消耗 binding 容量，不要求皮带可达。

Generic **output** 槽与上述 input 槽对称（F-BIND-R1-01）：每个可见输出槽的 domain = 真实外部源商品集 ∪ `__unused__` 哨兵，槽内 ExactlyOne；真实商品的全局出现次数由精确计数约束（sum == 需求量）决定。当前基地 52 需求 = 52 槽时计数自动逼满、哨兵恒 0（specs/04 §4.5 的满额结论不变）；需求小于槽数时多余槽合法空置（specs/03 端口空置规则）。哨兵是 binding 内部对象，`extract_port_specs()` 必须跳过它；`__unused__` 是保留名，不得作为商品出现在任何需求工件中，且 generic I/O 需求与无线槽数的装载是 fail-closed schema（双 section 必须在场、严格非负整数、默认装载路径按 canonical 商品角色校验，F-BIND-R1-02）。

**生产端对偶 (preprocess F-03)**：上面讲的是无线消费端（虚拟槽不进 routing），生产端同样要对偶处理。无线终品（canonical `commodity_metadata` 中 `sink_kind = "generic_input"`，即 positive `required_generic_inputs`，如 `qiaoyu_capsule`、`valley_battery`；它们只作 recipe output、从不作任何 recipe input，是纯终品）被无线消费、在 routing 网络里没有 sink，因此其**生产设施的实体输出口**（以及该 commodity 的任何 generic-output 口）也必须从 `extract_port_specs()` 排除——生产设施的原料**输入口**仍保留 routing。若把这些输出口导出成 routing terminal，会在 routing 里制造一个无 sink 的孤立 source，触发虚假 `front_blocked` / false-INFEASIBLE，错误拒绝合法布局。排除必须覆盖**所有**消费端口 front 可达性的位置：`extract_port_specs()`（routing/precheck 的入口）、RAB build-time 域过滤 `_filter_pose_binding_domain()` 与 RAB blocker 证书（F03-R3-01 教训：build-time 过滤是不经 port specs 的独立侧门）、routing deletion-core minimizer 的 oracle（必须消费由当轮 binding port specs 构造的 routing-visible port key 集，F04-R4-02）、pose-bool exact master 的 env 门控 port-active 输出需求 / hard-clearance 与 blocking-cell port cache / lazy-demand cut（输出侧需求与 cache 必须排除 routing-free 终品输出；visible 与 routing-free 混合输出侧不得按 raw 输出口泛化，F04-R4-03）、以及 separator-capacity / L2 抽象 routing / dynamic separator 的 commodity-side 分类（routing-free 终品绝不能被分类成 routed source，F04-R4-04）。另有语义 fail-closed 守卫：`sink_kind = "generic_input"` 商品一旦同时出现在任何 recipe input 中即拒绝（dual-role 会让本排除静默断真实消费者的料）——且该守卫必须覆盖**所有装载路径**：`validate_canonical_document()` 与直接 rules+plan 构建的 `validate_preprocess_context()` 双层（F04-R4-01 教训：overlay/直构路径曾绕过仅 canonical 一层的守卫）。

---

## 5.5 当前实例工件的正确阅读方式

### Certified exact 主线

只应读取：

- `mandatory_exact_instances.json`
- `generic_io_requirements.json`

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

它**没有**改变 certified exact runtime 的读取边界：

- certified runtime 仍读取冻结的 `mandatory_exact_instances.json`
- `PreprocessContext` 只是 preprocess 再生层的 build-time contract

