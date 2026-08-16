# W0 槽级算术到 binding+routing 排除的路径对应

> **当前状态：** `DISCHARGED_IN_PINNED_RESEARCH_PATH`
> **作用域：** 固定 `W0-ALIGNMENT`、固定矩形 `R=[1,6]×[51,57]`、钉死 current binding/routing research path。
> **性质：** model-correspondence evidence；不是游戏语义公理，不是 production certification。
> **机器 manifest：** [`06_MODEL_CORRESPONDENCE_MANIFEST.json`](06_MODEL_CORRESPONDENCE_MANIFEST.json)

## 1. 为什么需要单独的 lift

定理二证明的是一个抽象 binding contract：52 个席位、每席三标签 ExactlyOne、全局计数 34 与 18，因而所有席位都不能 `__unused__`。

要把这条槽级结论用于固定矩形排除，还必须证明当前 W0 research path 确实实现了同一个 contract，并把非 `__unused__` 选择解释为定理一所说的活动 source terminal。否则可能发生“数学定理正确，但实际 model/lowering/consumer 使用的是另一套对象”的翻译缝。

本页把该翻译拆成八条路径义务。定理二不依赖本页；终局排除依赖本页全部关闭。

## 2. 路径义务

| ID | 路径义务 | 独立证据 | 当前状态 |
|---|---|---|---|
| `W0-LIFT-01-INPUT-IDENTITY` | 固定 research path 消费与定理二一致的 W0 layout、candidate pool、mandatory instances、generic I/O 和 canonical rules。 | 定理二 checker 对六份承重输入逐字节核验；Phase -1 harness 的 `_load_frozen_inputs` 与 `_load_layout` 以同一路径和 hash-bound manifest 读入。 | `DISCHARGED` |
| `W0-LIFT-02-SLOT-COMPLETENESS` | binding model 构造且只构造定理二重导的 52 个 physical generic-output slots。 | `PortBindingModel._build_generic_output_domains` 只遍历 `boundary_io`/`protocol_core` 的 selected pose `output_port_cells`；A_BASELINE snapshot 中存在 52 个三变量 slot group。 | `DISCHARGED` |
| `W0-LIFT-03-PER-SLOT-EXACTLY-ONE` | 每个 source slot 的变量恰为 `blue_iron_ore/source_ore/__unused__`，并有一个 ExactlyOne。 | binding source 的 `slot_commodities = generic_commodities + ["__unused__"]` 与 `AddExactlyOne`；snapshot 对 52 组三变量逐组匹配 ExactlyOne。 | `DISCHARGED` |
| `W0-LIFT-04-GLOBAL-COUNTS` | model 对 52 个 blue literals 加 `sum=34`，对 52 个 source literals 加 `sum=18`。 | `_add_generic_output_requirements`；snapshot constraints 287/288 的变量集合、系数与 domain。 | `DISCHARGED` |
| `W0-LIFT-05-ACTIVE-PORT-EXPORT` | 非 `__unused__` 选择导出活动 source port spec，`__unused__` 不导出。 | `extract_selection` 读取 generic-output label；`extract_port_specs` 对 `None/__unused__` continue，对其他 label 追加 `type=out` port spec。 | `DISCHARGED` |
| `W0-LIFT-06-ROUTING-CONSUMPTION` | 固定路径把这些 port specs 与包含 strict rectangle 的 placement core 送入 exact routing precheck/solve，且不存在另一个绕过当前 binding model 的入口。 | Phase -1 `_new_binding_model`、`_occupied_core`、`_run_layout` 的单链调用；routing source hash。 | `DISCHARGED` |
| `W0-LIFT-07-CONTEXT-TRANSPORT` | 定理一可在定理二的增强 context 中继续使用。 | 两定理 problem/objective/layout 身份相同；定理二 `base_contextHash` 等于定理一 `contextHash`；新增前提只收窄合法 binding 集，不改变定理一的一格矛盾。 | `DISCHARGED` |
| `W0-LIFT-08-ENDPOINT-NONINTERFERENCE` | 本批只更新研究候选账，不改 exact status 或 stable claim ledger。 | 两份保护面 SHA-256 在 checker 前后相等。 | `DISCHARGED` |

## 3. Source-level 对应

### 3.1 generic-output 构造

`src/models/binding_subproblem.py::PortBindingModel._build_generic_output_domains` 执行：

1. 从 `required_generic_outputs.keys()` 取得两种 commodity；
2. 添加 `__unused__`；
3. 只接受 operation type `boundary_io` 和 `protocol_core`；
4. 对 selected pose 的每个 `output_port_cells` 建一个命名 slot；
5. 为三个标签各建 BoolVar；
6. 对该 slot 添加 ExactlyOne。

这与定理二的席位和 per-slot contract 同形。

### 3.2 全局计数

`_add_generic_output_requirements` 对每个 required commodity 收集所有 generic-output slot 上的同名 literal，并添加：

```text
sum(vars_for_commodity) == required
```

W0 pinned generic I/O 给出 required 为 34 与 18。A_BASELINE snapshot 的 constraints 287 和 288 独立显示两组各 52 个系数 1 的 literal，以及 domains `[34,34]`、`[18,18]`。

### 3.3 活动 port 映射

`extract_selection` 对每个 generic-output slot 提取唯一被选 label。`extract_port_specs` 在 label 为 `None` 或 `__unused__` 时跳过；否则把该 physical slot 追加为 `type="out"` 的 source port spec。

因此在当前路径中：

```text
slot != __unused__
    iff
该 physical generic-output slot 进入 routing port specs
```

对于 `boundary_port_041:out:0`，这正是定理一的 `Active_041`。

## 4. Routing 与 strict rectangle

Phase -1 固定布局路径先由 `_occupied_core` 把固定矩形的 42 个 cells 作为 `__ghost_rect__` owner 加入 routing obstacle core，再从 binding model 提取 `port_specs`，依次调用 exact routing precheck 和 `RoutingSubproblem`。

定理一的独立 checker从 canonical 和固定输入重导：041 的唯一 front cell 为 `(1,53)`，该格在矩形内；活动 source 要求 belt terminal，而 strict-empty 禁止任何 logistics occupant。因此任意包含 041 source port spec 的 routing witness 都不存在。

## 5. Context transport

定理一的 base context 量化任意 binding selection，并证明：

\[
Active_{041}(b)\Longrightarrow\neg\exists r\,Routable_{P5}(b,r).
\]

定理二的 context 保留定理一全部 problem、objective、layout、rectangle 和规则字节，只增加“`b` 满足 W0 binding contract”的前提。由前提弱化的单调性，定理一在增强 context 中仍成立。

该 transport 不是“两个 hash 看起来相似”；checker 必须验证：

```text
theorem_two.base_contextHash == theorem_one.contextHash
```

并逐项核对共享 input identities。

## 6. 声明边界

即使八条义务全部关闭，得到的也只是：

> 固定 W0 layout 与固定矩形在钉死的 current binding+routing research model 中没有 `(binding,routing)` witness。

它不证明 current binding contract 与完整 adjudicated-game 绑定语义等价，不写 production exact status，不进入 certified frontier，也不外推其他矩形或布局。
