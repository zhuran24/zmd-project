# 文档职责收束验收报告

> 本页由当前 `DOC_POLICY.json`、前门注册表、section registry 与 Markdown 链接图自动生成；禁止手工修改。
> 文档系统版本：`2.6.0`；验收状态：`PASS`；审计摘要：`sha256:22e3b06d387678af720f22e1eacfd7ab3594dd93d4c638b5bf04f6c647c074b1`。

本页回答第三阶段是否已经消除局部孤岛、重复职责、手写易变状态和经退役入口下钻。它不授予项目 authority，也不把历史证据提升为 current。

## 验收总览

| 项目 | 结果 |
|---|---:|
| current Markdown | 132 |
| 显式 section | 14 |
| 生成式兼容入口 | 14 |
| 重复 current 职责组 | 0 |
| 手写易变状态命中 | 0 |
| current → retired redirect 链接 | 0 |
| 阻断项 | 0 |

## Section 局部可达性

每个非兼容跳转的 current 成员都必须从它声明的局部入口，经同一 section 内的 current Markdown 链接可达。

| Section | 入口 | 成员 | 可达 | 不可达 |
|---|---|---:|---:|---:|
| `repository-navigation` | `README.md` | 7 | 7 | 0 |
| `knowledge` | `data/knowledge/README.md` | 9 | 9 | 0 |
| `documentation-framework` | `docs/governance/document-system/ARCHITECTURE.md` | 30 | 30 | 0 |
| `project-manual` | `docs/项目说明/README.md` | 19 | 19 | 0 |
| `specifications` | `specs/README.md` | 25 | 25 | 0 |
| `operations` | `docs/OPERATIONS.md` | 8 | 8 | 0 |
| `research-archive` | `docs/research/README.md` | 2 | 2 | 0 |
| `history-archive` | `docs/history/README.md` | 7 | 7 | 0 |
| `topic-guides` | `docs/subjects/README.md` | 4 | 4 | 0 |
| `formal-verification` | `formal/README.md` | 1 | 1 | 0 |
| `certification` | `docs/CERTIFICATION.md` | 6 | 6 | 0 |
| `compatibility-adapters` | `docs/compatibility_matrix.md` | 4 | 4 | 0 |
| `repository-governance` | `data/repository_governance/README.md` | 1 | 1 | 0 |
| `implementation-navigation` | `NAV_MAP.md` | 2 | 2 | 0 |

## 阻断项

- 无。当前职责图满足登记的第三阶段收束不变量。

## 保留边界

- `PASS` 只表示当前文档职责层通过本页列出的结构验收，不表示数学结论、phase gate、release 或 certification 通过。
- 历史文档可以保留旧状态、哈希和收据；它们不进入 current 图。
- 新 current 文档仍必须先获得精确 policy、section 归属和局部入口链接。
- 改变检查语义时必须更新不变量、ADR、架构、维护指南、迁移与测试。

重建并验收：

```bash
.venv/bin/python devtools/docctl.py render-convergence --write
.venv/bin/python devtools/docctl.py doctor
```
