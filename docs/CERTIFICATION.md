# 认证与发布边界入口

本页只负责把认证相关问题路由到唯一权威、稳定合同和机器投影。它不复制当前 gate、hash、上下界、测试收据或 owner decision。

## 权威顺序

- 最高仓内认证边界：[`PROJECT_LOCK.md`](../PROJECT_LOCK.md)
- 当前机器与知识状态：[`CURRENT.md`](CURRENT.md)
- 稳定 phase-gate 解释合同：[`PHASE_1_2_CLOSE_GATE.md`](PHASE_1_2_CLOSE_GATE.md)
- GO / close 词汇与证据边界：[`项目说明/12_go_criteria.md`](项目说明/12_go_criteria.md)
- certification-side 操作入口：[`certside/README.md`](../certside/README.md)
- canonical semantics binding：[`certside/binding_canonical_semantics_v1.md`](../certside/binding_canonical_semantics_v1.md)

## 不可合并的层

证明、checker、formal build、solver status、owner gate、durable seal 和 public publication 分别属于不同层。低层结果不能自动提升为高层 authority。遇到冲突时，以 `PROJECT_LOCK.md`、机器 authority 和显式 owner decision 的管辖范围为准。

## 修改纪律

普通文档维护不得修改 owner-only authority。修改本入口只允许调整稳定导航或解释；当前值必须从结构化源重新生成。

```bash
.venv/bin/python devtools/docctl.py context docs/CERTIFICATION.md --intent edit
.venv/bin/python devtools/docctl.py check --changed
```
