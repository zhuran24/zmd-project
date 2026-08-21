# Round-1 LOW findings dispositions

外审 SHA-256：`6531c0e5a1796ee8ab7ca04affaddcded7bd47af1f76b3d2fd7564c1229276bd`

## LOW 1: F6 —— 反硬编码的那一半 gate 是字符串装饰【LOW】

`scripts/check_p1_2_proof_obligations.py:14355`：

```python
if '{"boundary_io", "protocol_core"}' in output_domain_source:
```

换个元素顺序、写成 `frozenset(...)`、提成模块级常量、或者放进 `_build_generic_input_domains`，都能绕过。真正起作用的是它旁边那条 AST 正向义务（`_direct_calls_attr`），而对应的变异测试 `test_package_checker_rejects_production_provider_hardcode` 打的也正是 AST 那条——所以这条字符串检查从未被测试过，只提供了「硬编码被结构性禁止」的错觉。

**处置：`DEFERRED_LOW`。** 外审将其定为 LOW，未显示可导致错误 negative cut；本轮不扩 scope，保留原文和复审触发，要求第二轮确认该理由。

## LOW 2: F7 —— funnel / contract / transport 的义务侧仍是源码子串匹配，不是结构判定【LOW】

- `:14114-14122` 用 `required_source not in funnel_source` 检查 funnel 是否传了 `artifact_hashes=self.artifact_hashes`、`binding_semantics_contract=(` 等；
- `:14106-14113` 用 `funnel_source.find(...)` 的**文本位置**比较 `reverify_pos > mint_pos` 来判定「先复验后铸造」；
- `:14130-14139` 用子串检查合同函数里出现了 `inspect.signature(...)`；
- `:14305-14309` 用子串检查 transport 里出现了 `"-I"`、`"-B"`、`pycache_prefix=`、`timeout=float(timeout_seconds)`。

以上都能被注释或死代码满足，文本先后也不等于控制流先后。需要说明的是：**禁止侧（import graph、动态执行原语、`sys.modules`、`self.master`/`self._solver`、包文件集合、四层真调用链、`build()` 约束族集合）确实是真 AST**（`:14188-14252`、`:14283-14346`），比旧的 226 行 token checker 强了一个量级；残留的字符串匹配集中在义务侧。旧 checker 删除后我没有找到检查缺口——被删的锚点都是被算术重写作废的 CP-SAT 搜索参数项，`os` 在包内仍被禁，`test_p1_2_checker_rejects_env_reader_in_infeasibility_reverifier` 这个测试也仍然存在（只是从 JSON 锚点列表里移出）。

**处置：`DEFERRED_LOW`。** 外审将其定为 LOW，未显示可导致错误 negative cut；本轮不扩 scope，保留原文和复审触发，要求第二轮确认该理由。

## LOW 3: F8 —— `getattr` / `setattr` 不在动态原语拒绝清单里【LOW】

`forbidden_dynamic_names = {__import__, compile, eval, exec, globals, locals, vars}`（`:14174-14182`）。`sys.modules` 的禁令是 `ast.Attribute(value=Name("sys"), attr="modules")` 匹配（`:14237-14243`），一次 `getattr(sys, "modules")` 间接就绕开了。同理 `getattr(__builtins__, ...)` 里 `__builtins__` 作为 `ast.Name` 会被抓，但 `getattr(sys.modules[...], ...)` 这类组合值得一并堵上。威胁模型是自己人重构漂移而非攻击者，故 LOW。

**处置：`DEFERRED_LOW`。** 外审将其定为 LOW，未显示可导致错误 negative cut；本轮不扩 scope，保留原文和复审触发，要求第二轮确认该理由。

## LOW 4: F9 —— 合同的 plan 映射用 `{}` 兜底，会写出一句关于 plan 的假陈述【LOW】

`benders_loop.py:6694-6696` 写 `dict(snapshot_kwargs.get("generic_output_slots_by_operation", {}))`。当 `required_generic_outputs` 为空时该 kwarg 根本没被放进 `snapshot_kwargs`（`:6632-6636` 有 `if` 门），于是合同断言「plan 声明了零个 generic-output provider」——这与 plan 事实不符。I1 会当成 `SEMANTICS_CONTRACT_OUTPUT_PLAN_DRIFT` 拒掉（安全方向），但这是**误打误撞**触发的守卫，且意味着在 `required_generic_outputs` 为空的快照上 I1 永远无法 confirm。今天不活（当前需求 52 槽）。

**处置：`DEFERRED_LOW`。** 外审将其定为 LOW，未显示可导致错误 negative cut；本轮不扩 scope，保留原文和复审触发，要求第二轮确认该理由。

## LOW 5: F10 —— `test_binding_overload_separation_override.py` 模块 docstring 已过期【LOW】

docstring 说「I1 passes use_overload_separation=False」，而新 I1 根本不再构建 production 模型；同文件最后一个测试自己承认了这一点（"I1 no longer rebuilds the production model, so the overload env is inert"）。前后自相矛盾。

**处置：`FIXED`。** F1 已改为 production runtime observation，并加入结构红测和单调松弛证书字段。

## LOW 6: F11 —— handoff §5 的「focused I1/sidecar/contract suite 43 passed」不可从 §7 的命令复现【LOW，文档】

按 §7 给的四文件命令实测 **39 passed**；加上真实 parity 文件是 41 collected。43 这个数对应的命令集合在 handoff 里没有给出。ruff / proof-obligation checker（15 obligations / 73 sinks）/ strong-status（65 AST nodes / 83 entries）/ 真实 parity（2 passed）我都独立复现，与声明一致。

**处置：`FIXED`。** README、基线归因和第二轮 handoff 已按真实边界改写。

## LOW 7: F12 —— `routing_deletion_core_minimizer.py` 里有一份活着的 generic-input provider 硬编码集合【LOW，先前存在】

`src/search/routing_deletion_core_minimizer.py:38-39`：`_GENERIC_INPUT_PROVIDER_OPERATIONS = frozenset({"box_sink", "protocol_core"})`。只在 `visible_keys is None` 的遗留 fallback 分支（`:133-135`）里用，效果是跳过该 instance 的 terminal（保守），且唯一 production caller（`benders_loop.py:7642`）总是传实参，整条路径还在 `EXACT_B1_DELETION_CORE_CUT` 后面。不是这批引入的，但它属于「provider 集合硬编码」这一类，登记在案。

**处置：`FIXED`。** F2 已删除四份手抄表，改为 preprocess plan 与 authoritative instances 派生。
