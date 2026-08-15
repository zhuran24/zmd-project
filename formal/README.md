# `formal/`：Lean 4 形式化验证工作区

本目录保存研究层的机器检查陈述、构建配置和公理审计。它提供可重放的形式化证据，但**不自行改变 production certification、phase gate 或 `PROJECT_LOCK.md` 的权威边界**。

## 从哪里开始

- 认证与发布边界：[`PROJECT_LOCK.md`](../PROJECT_LOCK.md)
- 当前 claim、dossier 与证据坐标：[`docs/CATALOG.md`](../docs/CATALOG.md)
- 形式化头启动设计与作用域：[`p3_0_formal_verification_head_start_design_v1.md`](../docs/research/p3_0_formal_verification_head_start_design_v1.md)
- 旧版完整模块说明与逐定理表：[`formal_readme_pre_phase3_batch3_20260812.md`](../docs/history/formal/formal_readme_pre_phase3_batch3_20260812.md)

## 当前载荷

- `ZmdFormal/` 与 `ZmdFormal.lean`：Lean 模块与入口。
- `axiom_audit.lean`：定理公理依赖审计。
- `lakefile.toml`、`lake-manifest.json`、`lean-toolchain`：固定构建环境。

旧版 README 记录了当时的定理清单、外审回收和路线队列。它已按字节保留为历史证据；本入口不再手抄会继续变化的定理数量、审阅状态或 phase 叙事。

## 重放

```bash
cd formal
lake update
lake exe cache get
lake build
lake env lean axiom_audit.lean
```

工具链和依赖以本目录的锁文件为准。构建成功只证明对应 Lean 载荷在锁定环境中可检查，不等于 owner 已将其纳入认证 TCB。

## 修改纪律

修改 Lean 陈述、构建锁或本入口前，先查询目标路径：

```bash
.venv/bin/python devtools/docctl.py context formal/README.md --intent edit
```

命题、作用域或前提发生实质变化时，必须通过稳定 claim、evidence 与必要的 supersession 关系表达；不要只在 README 中改写历史结论。完成后运行操作卡列出的检查。
