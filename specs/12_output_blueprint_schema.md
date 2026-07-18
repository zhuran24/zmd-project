---
status: CURRENT_CODE_ALIGNED
source_of_truth: src/io/output_schema.py, src/io/serializer.py, src/io/delivery_manifest.py, src/search/certified_surface.py, src/search/terminal_fixed_witness_verifier.py
last_verified_against: 2026-07-18
owner: output-layer
---

# 12 蓝图输出结构与发布权限

## 12.1 两个不同问题

本章同时记录 JSON 结构和写入 authority。结构合法不等于认证发布合法：任意调用者都可以
在非 canonical 路径构造一个 schema-valid blueprint，但只有 verified publisher 从
supervisor-sealed campaign 事务式写出的 canonical 三件套才具有 public certified 语义。

canonical 路径为：

- `data/solutions/final_solution.json`；
- `data/blueprints/optimal_blueprint.json`；
- `data/solutions/certified_delivery_manifest.json`。

`src/io/serializer.write_blueprint_payload()` 和 `export_certified_blueprint()` 会拒绝普通调用者
写 canonical `optimal_blueprint.json`。正式发布必须经过
`src/search/certified_surface.py:publish_verified_certified_delivery_surface()`。

## 12.2 Blueprint 根结构

`optimal_blueprint.json` 的 canonical 根对象包含：

```json
{
  "metadata": {},
  "objective_achieved": {},
  "facilities": [],
  "routing_network": {}
}
```

`normalize_blueprint_payload()` 会重建并规范化这四个域；未知根域不会成为 canonical 输出。

## 12.3 Metadata 与目标

`metadata` 必含非空 `export_timestamp`，并规范化：

- `version`；
- `solve_time_seconds`；
- `benders_iterations`；
- `export_timestamp`。

`objective_achieved.empty_rect` 包含 `w`、`h`、`anchor_x`、`anchor_y`、`score`。
从 terminal result 构造 certified blueprint 时，anchor 必须存在且非负。`score` 当前由空矩形
area 派生；认证目标仍以 campaign 的 `max_lex(area, min_side)` 证据为准，不能只看此展示字段。

## 12.4 Facilities

每个 facility 规范化为：

- `instance_id`；
- `facility_type`；
- `anchor: {x, y}`；
- `orientation`；
- `port_mode`；
- `active_ports`。

active port 的 `type` 只能为 `input` / `output`，方向只能为 `N` / `S` / `E` / `W`，并带
坐标与 commodity。serializer 从 terminal `placement_solution` 和当前 candidate pools 恢复
facility 几何；找不到唯一可解释的 pose 时应失败，而不是猜测。

certified `active_ports` 不得从 pose 的全部物理口推断。terminal fixed-witness verifier 将实际
绑定选中的规范化 `port_specs` 连同 `port_specs_digest` 写入 durable audit；capsule 在封存
`CERTIFIED` 前校验其结构、数量、摘要、去重和实例归属，失败即降级为 `UNPROVEN`；verified publisher
只能在 project-bound seal/replay 验证后读取该 carrier，并显式传给 certified serializer。
未绑定的 pose 槽（包括贴边 pose 的出界槽）不导出。任何 active port 出界、引用未知实例、
不属于所选 pose 的对应方向/类型槽，或擅自改写 concrete commodity，均须 fail closed。

## 12.5 Routing network

routing payload 被规范化为 ground/elevated 层的坐标映射。组件类型受
`belt`、`splitter`、`merger`、`bridge` 集合约束，方向字段使用四向枚举。该 JSON 是离散 routing
结果的投影，不是连续 flow diagnostic 的输出。

## 12.6 Canonical publication contract

中央 publisher 的顺序是：

1. 从 canonical campaign path 重读 supervisor-sealed state；
2. 验证 resume/current-hash、terminal frontier、sink replay、fixed witness 与 publish-open gate；
3. 从 verified terminal result 与 digest-bound fixed-witness `port_specs` 构造
   `final_solution` 与 blueprint；
4. 原子写入两份 payload；
5. 构造并校验 delivery manifest，使其绑定同一 campaign 与文件哈希；
6. 再运行 public-surface verifier；
7. 任一步失败则清理 canonical 三件套。

因此，下游不能仅因文件名是 `optimal_blueprint.json`、字段含 `CERTIFIED`、或 schema validator
通过，就把文件当成 public certified artifact。必须以 `evaluate_certified_delivery_surface()`
的 fail-closed verdict 为准。

## 12.7 非权威副本

viewer bundles、IndustrialPlanner exports、reports、legacy render payloads 和 caller-selected
output paths 都是派生/兼容面。它们可以复用 schema 或相同文件名，但目录、provenance 和状态
必须明确为 non-authoritative，不能反向打开 campaign、phase gate 或 public publication。
