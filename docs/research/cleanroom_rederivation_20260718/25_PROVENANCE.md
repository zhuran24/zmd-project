# 25 — R-* 价签精算回件（2026-08-04）来源与性质

| 项目 | 值 |
|---|---|
| 收件时间 | 2026-08-04 |
| 通道 | owner 于 2026-08-04 把 GPT Pro 会话产出的交付包（zip）喂入主线线程 |
| 存档内容 | `25_rstar_pricetag_delivery_20260804/`（14 个文件，逐字复制，未做任何改动） |
| 回件 zip | `~/下载/rstar_pricetag_delivery_20260804.zip`，74,919 B，SHA256 `67ea8d83a1065d63f0524c1141888f8b8e705f4f4a4802303b586f119d5c2e2d` |
| 送出的提问包 | `w0_rstar_pricetag_20260804.7z`，45,599 B，SHA256 `025d84559de546b1576997b10c1a879248a1f5ba4e4d27baed8644afea57da35` |
| 提问包源目录 | `.artifacts/w0_consult_packs_20260804/rstar_pricetag/`（`00_ASK.md`、`01_charter_full.md`、`02_methodology_0b.md`、`03_slack_audit_table.md`、`04_derived_theorems.json`、`05_strict_evidence_summary.md`、`06_geometry_constants.md`、`07_current_state.md`、`08_original_domain_baseline.md`） |
| 包内自带清单 | `MANIFEST.sha256`（13 条），存档后逐条校验通过（`sha256sum -c`，13/13 OK） |

## owner 转述的交付摘要要点

- 交付包按 `00_ASK.md` 给九条 `R-*` 限制各做了一份价签：来源分类、依据的零余量账、
  定性与定量价格（含口径）、前提集、买回了什么、产率评级、撤退线、证据等级。
- 主报告 `RSTAR_PRICETAG_REPORT.md`，另附四份可直接套用的补丁：A（九行总表）、
  B（`04_derived_theorems.json` 只增不改的 JSON 片段）、C（2 条无条件行 + 5 条 G1 条件行）、
  D（九份判定实验规格，含伪代码/常量/规模/预算/三分判读）。
- 包内自带三个脚本：`apply_price_tag_patches.py`（幂等应用 B/C，拒绝覆盖不同旧值）、
  `price_tag_arithmetic_audit.py`（标准库复算候选域与关系域数字）、`validate_delivery.py`
  （结构/JSON/旧字段保持/幂等/关键算术自校验），结果落 `*_results.json`。
- 对方自述 `authority=false`、不登记任何界、账本不变；本批实际执行的是无求解器算术与
  坐标枚举，补丁 D 里的 CP-SAT 项是纸面规格、未施工。
- 对方自述所有百分比都绑定冻结基线 `H0`（`5012845367e2…` 与 `545b98c2b4f9…`），
  并分别标明候选位姿 / 矩形见证 / 覆盖关系 / catalog 口径，强调它们不能相加成一个
  全局「解被删比例」。

## 性质与边界

**research-only 外脑产出，未经我方核实。** 本目录只做逐字存档，不构成复核结论：

- 包内所有【已证明】标注、算术数字、产率评级、撤退线均是对方自述，本文书写就时
  尚未做独立复算或对抗审查；引用任何一条前必须先自己算。
- 不携带任何 authority：不改变 `U=(1188,18)`、`L=absent`，不触碰 cut / production /
  certified 状态，也不触碰 `PROJECT_LOCK.md` 的任何 `F-*`/`PCR-*`/`CUT-*` 条款。
- 包内 patch A-D 与三个脚本**未被应用**到仓库内任何文书；`03_slack_audit_table.patched.md`
  与 `04_derived_theorems.patched.json` 是对方在其源包上算出的结果，属回件的一部分，
  不是我方 `docs/` 下相应文件的新版本。
- 先例纪律（19 号、147.4 两次）：外脑推理文书入库不等于采信，承重引用前要过 refute 席，
  数字前提要标证据等级。
