# 实验三：W0 席位算术引理与固定矩形终局排除

> **当前状态：** `THEOREM_TWO_IMPLEMENTED_PENDING_POSTCOMMIT_RECEIPT_AND_TERMINAL_COMPOSITION`
> **日期：** 2026-08-16
> **性质：** `research_only / non_authorizing`

本目录承载实验一的第二条离线定理及其与第一条定理的组合终局主张。验收判据已先行冻结；当前新增定理二的 Judgment、证明与独立 checker，post-commit 收据和终局组合仍待后续提交。

## 冻结入口

- [`00_OWNER_AUTHORIZATION_20260816.md`](00_OWNER_AUTHORIZATION_20260816.md)：本批窄授权与非蕴含边界；
- [`00_ACCEPTANCE_CRITERIA_FROZEN.md`](00_ACCEPTANCE_CRITERIA_FROZEN.md)：不可回改的验收标准；
- [`01_CONTEXT_MANIFEST.json`](01_CONTEXT_MANIFEST.json)：问题、目标、上下文、输入、前代定理、覆盖与路径证据身份。

## 定理二实现

- [`02_JUDGMENT.json`](02_JUDGMENT.json)：52/34/18 席位算术 Judgment；
- [`03_PROOF.md`](03_PROOF.md)：不依赖实验数据的有限计数证明；
- [`04_check_w0_slot_arithmetic.py`](04_check_w0_slot_arithmetic.py)：纯标准库独立复算器，支持 coverage off／required 双模式与负测试。

本目录当前尚不表示 W0 固定矩形已经获得终局排除；该结论必须等待 theorem receipt 与路径级 lift checker 闭合。
