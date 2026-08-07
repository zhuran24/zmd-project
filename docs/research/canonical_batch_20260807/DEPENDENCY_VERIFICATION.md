# candidate_placements 与派生工件依赖验证（2026-08-07 canonical 修正批）

结论先行：**candidate_placements.json 不需重生成；全部派生 preprocess 工件字节不变。**
以下是逐行证据（读的是本 worktree 源码，非假设）。

## 1. 池子生成器读 canonical 的哪些字段

`src/placement/placement_generator.py`：

- `load_templates()`（**:468-477**）：`load_strict_json` 读整份 canonical（:475），
  对全文件做 jsonschema 校验（:476，schema=`rules/canonical_rules.schema.json`），
  然后 **只返回 `rules["facility_templates"]`**（:477）。
- `generate_all_pools(templates)`（**:480-523**）：仅按每个 template 的
  `dimensions/w/h` 与 `port_rule` 分派枚举（`_validate_template_geometry_contract`
  :487 + 五个 port_rule 分支 :489-520）。不读 `semantics`、不读 `globals` 之外的任何
  新增段（网格常量在生成器模块内部常量）。
- `main()`（:526-）把 pools 写 `candidate_placements.json`。

本批 `facility_templates` 段与 HEAD **byte-identical**（机器断言，见 §3），故池子输入
不变 → 池子不需重生成。生成器与本批唯一的交互面是 :476 的 jsonschema 校验——新增
内容全部在 `semantics` 段内，schema 该段 `additionalProperties: true`（schema:431-434），
校验已实测通过（见 §3）。

先例对齐：08-05 emptiness 批（5f1b974）同一结论（"empty_rectangle 不被
preprocess/placement 消费，派生工件字节未变"）；本批消费面还要更窄（semantics-only）。

## 2. preprocess 派生链读 canonical 的哪些字段

`src/interchange/preprocess_context.py`：

- **:161-163** `globals` → `time` / `logistics`；
- **:171-173** `facility_templates`（缺失即 raise）；
- **:188-190** `recipes` / `production_targets` / `commodity_metadata`；
- **:25 + :183** additive-only fail-closed 作用于 `rules/preprocess_plan.json` 顶层
  （`recipes`/`production_targets`/`commodity_roles`）——本批不动 preprocess_plan.json，
  该守卫不触发；
- `semantics` 段零引用（全仓 `rg '"semantics"' src/ scripts/` 仅命中
  `exact_coordinate_master.py` 的 cut-lowering 内部标签字符串，与 canonical 无关）。

`metadata.version` 流入 `context.metadata["source_rules_version"]`（pin 于
`src/tests/test_preprocess_context.py:61`，并内嵌于 tracked 派生工件
`data/solutions/current_preprocess_context.json:5`）——本批**刻意不 bump version**，
故该工件与测试 pin 均不变。`current_preprocess_context.json` 不内嵌 canonical sha
（rg 实测零命中）。

## 3. 机器断言（可复现）

worktree 内实跑（输出摘录）：

```
$schema/metadata/globals/routing_rules/facility_templates/recipes/
production_targets/commodity_metadata: 八段与 HEAD identical
all pre-existing semantics fields byte-identical (additive-only confirmed)
new entries: ['axiom_kernel', 'port_commodity_scope', 'rate_lemma_scope']
strict load OK / jsonschema validate OK / pydantic parse OK (version=1.2.0)
```

复现命令：对 HEAD 版与工作版逐段 `==` 断言（json.load 后逐顶层键比较 +
现有 semantics 条款逐字段比较），再用 `src/io/strict_json.load_strict_json` +
`jsonschema.validate` + `CanonicalRulesDocument.model_validate` 三链解析。

## 4. 外部工件状态

worktree 初始缺 `data/preprocessed/candidate_placements.json`（lightweight checkout
常态）；已用 `scripts/restore_external_artifacts.py candidate_placements --source
/home/zhuran24/zmd-pj/data/preprocessed/candidate_placements.json --force` 恢复，
恢复后校验 = 54,467,709 B / SHA256 `f05b1291a51d…`（与 pin 一致，工具自动 verify）。
该文件 gitignored，不入提交。
