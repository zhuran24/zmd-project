# MATHEMATICAL_FOUNDATIONS.md — SUPERSEDED

> **Status**: 2026-05-23 拆分重组到项目顶层 `docs/项目说明/`. 本 file 仅留 redirect stub, 不再 update.

## 重组目的

原 math doc 1580 line 跟 `PHASE_POST_1_1_REFACTOR_PLAN.md` 1449 line 二份 doc 数学原理 + 死路 paradigm 重合 ~30-40%, 维护双倍. 用户决策: 改成项目顶层 `docs/项目说明/` 文件夹 (21 sub-doc 中等粒度), 各 sub-doc 各管一摊, 不重复.

## 新位置

`docs/项目说明/` (项目顶层) — 跟 `docs/research/` 平级.

入口: `docs/项目说明/README.md` 含总索引 + 受众分流 + 21 sub-doc 文档地图.

## 内容 mapping (本 file 原 section → 新 sub-doc)

| 原 section | 新位置 |
|---|---|
| §0 文档目的 + 受众 | `docs/项目说明/README.md` (合进总索引) |
| §1 数学问题陈述 | `docs/项目说明/01_overview.md` (跟 plan §1 合并) |
| §2 已确定核心数学 paradigm | `docs/项目说明/02_mathematical_foundations.md` |
| §3 各 family 数学基础详 (F1-F9) | `docs/项目说明/02_mathematical_foundations.md` (cont) |
| §4 已 verify 不通的 paradigm | `docs/项目说明/03_paradigm_death_baseline.md` (跟 plan §4 合并) |
| §5 待定 mathematical questions (33 Q) | `docs/项目说明/05_open_questions.md` (跟 plan §17 合并) |
| §6 数学层验证 workflow | `docs/项目说明/16_workflow_review.md` (跟 plan §22 合并) |
| §7 跟相关 spec / doc 关系 | `docs/项目说明/README.md` (合进总索引) |
| §8 文档维护 | `docs/项目说明/README.md` (合进总索引) |
| §9 引用 / refs (含学术 reference) | `docs/项目说明/21_glossary.md` (跟 plan Appendix A 合并) |

## Git 历史

完整 commit 历史详 `git log -- docs/research/p3_b_design_v2_20260521/MATHEMATICAL_FOUNDATIONS.md`. 关键 commit:
- `af83885` — 初版 1580 line (10 section, 含 9 family 数学根据 + 27 lever 死路按数学分类 + 33 open Q)
- 本 commit — superseded by docs/项目说明/

旧 math content 100% 进新位置, 无丢失.
