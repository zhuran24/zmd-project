<!-- _authority: NON_FROZEN_DERIVED | 非冻结派生件 -->

# `rules/derived/` 非冻结派生层

本目录是规则系统重设计线的 L2（派生规则层）。owner 已在 `OWNER_DECISION_SUMMARY.md` 头部 2026-08-15 裁定追记中接受八件之第 4 件，登记提交为 `3d34687cd244e82fda41ff18b88171e7b45298b1`：`rules/derived/` 可以作为 `rules/` 下唯一的非冻结派生子目录存在。

这项裁定只改变本目录的准入边界，不改变相邻文件的身份：`rules/canonical_rules.json`、两份 schema、`preprocess_plan.json` 及其 schema 仍是既有冻结／owner-only 表面。本目录不是 canonical，不参加 freeze-ritual，不拥有 owner authority，也不能被引用成 certified 前提。自动生成或新建的条目默认 `UNREVIEWED`，过独立拒真／反例席后才能转 `ACTIVE`。

## 目录合同

- `derived_rule.schema.json`：单条 L2 条目的形态合同。schema 能检查字段和状态形状，不能证明字段内容正确。
- `entries/<id>.json`：一条目一文件；文件名必须等于 `<id>.json`，避免多会话共同改一只大 JSON。
- `ruling_index.jsonl`：`OWN-M*`／`SIM-*`／`W-*` 的 append-only（只追加）纯抽取事件索引；它是定位器，不是原裁决的替代权威。
- `facility_template_gap.json`：vendored IndustrialPlanner 顶层实体 id 与 canonical `facility_templates`、显式 adapter target 的差集。`NOT_DIRECTLY_REGISTERED` 只是候选覆盖缺口，不等于“模型必然表达不了”。
- `manifest.json`：状态机、D-21 指纹规格、tracked 产品和未来打包白／黑名单声明。

每个文件必须带 `_authority: NON_FROZEN_DERIVED` 头。本 README 用首行注释表达；JSON 用根对象第一个字段；JSONL 用第一条 HEADER 记录。

## 状态机

```text
UNREVIEWED → ACTIVE → STALE → ACTIVE
          ↘ RETIRED / SUPERSEDED
ACTIVE / STALE → PROMOTED
```

- `UNREVIEWED`：扫描或立架默认产物。不得进入承重前提集，指纹漂移只显示、不阻断。
- `ACTIVE`：已过独立拒真／反例席。前提漂移后转 `STALE`。
- `STALE`：只有存在 consumers 时才阻断消费；没有消费者时不把 canonical 批拖成线性清账。
- `RETIRED`／`SUPERSEDED`／`PROMOTED`：终态；不得静默改回活跃状态。

## D-21 前提指纹

实现位于 `devtools/rule_system_tooling.py`，读取 JSON 时直接复用 `src.io.strict_json.load_strict_json_exact_decimal`：

1. 对象键排序；数组保持语义顺序。
2. 字符串统一 NFC，换行统一 LF。
3. JSON 整数、十进制 token 与 `{ "exact_rational": "p/q" }` 全部化成约分后的精确有理数，不经过二进制 float。
4. `source_value` 前提指纹取路径、JSON Pointer 和现场值；另行比较 `value_at_derivation`，防止只重算指纹把历史取值悄悄洗掉。
5. `assumption` 无现场数值，指纹取规范化 statement 与显式 `assumption_version`，不得编造占位数字。
6. `derived` 前提取被引条目 id、level 和其 `premise_fingerprint`。
7. `semantics._epoch`、canonical schema SHA、mtime、绝对路径、locale 均不得进入指纹。

第 3 件“canonical schema SHA 怎样钉”仍待 owner 裁，属于批 2。本批的 currency（新鲜度）测试不会顺手建立该 pin。

## 工具与重算

所有命令使用项目解释器：

```bash
.venv/bin/python devtools/rule_system_tooling.py check
.venv/bin/python devtools/rule_system_tooling.py check-ruling-index
.venv/bin/python devtools/rule_system_tooling.py check-facility-gap
.venv/bin/python devtools/rule_system_tooling.py check-derived
.venv/bin/python devtools/rule_system_tooling.py check-views
.venv/bin/python devtools/rule_system_tooling.py fingerprint \
  rules/derived/entries/D-B1-SCAFFOLD-001.json
```

生成器以 stdout 输出确定性字节，由批次执行席在取过目标路径 `docctl context` 后写入 tracked 文件。currency 测试重新冷启动生成并逐字比较，不信文件时间戳。

## 打包边界

`manifest.json.package_declaration` 已列出未来快照应显式纳入与排除的路径，但 `scripts/package_review_snapshot.py` 尚未接线。本批按 owner 边界把接线登记为 `OD-B1-PACKAGE-01`，不修改 `scripts/`。在欠账关闭前，不能声称标准外审包已经自动纳入本目录。

## 仍待 owner 裁的事项

2026-08-15 只批准了第 4 件。本目录不得借立架顺带宣称其余七件获批，尤其不得：

- 钉 `rules/canonical_rules.schema.json` 的 SHA（第 3 件，批 2）；
- 把形态／凭据 checker 接成 CI 硬门（第 5 件）；
- 修改 §0b 三处正文（第 6 件）；
- 新增运行时代码埋点（第 7 件）；
- 把拒真席默认排法写成全项目已批准制度（第 8 件）。
