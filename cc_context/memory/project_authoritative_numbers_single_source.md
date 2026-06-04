---
name: authoritative-numbers-single-source
description: "评审包/文档反复出现的权威数字 (cuts 计数 / sizing / F3 / remap) 与 cut-family canonical SoT 校验, 都落成\"核心节点(主体)+ 投影 + 强制函数\"架构 (用户 2026-06-04 指定, 同 memory-currency-protocol 给 handoff 的做法)。治反复 reset 审查的 doc-currency 长尾 + SoT 私有副本发散。"
metadata: 
  node_type: memory
  type: project
  originSessionId: ca5783d1-e3be-4591-8cfd-4ede5ed83635
---

用户 2026-06-04 要求把"主体为核心节点、其余是它的投影"这套架构 (本就给 memory 用, 见 [[memory-currency-protocol]] rule1/2 + stamp_living_status) **也套到项目文档/数字上**。两件事 (Design A + B) 落地, 都用 **core-node + projection + forcing-function**。**诚实现状 (v28 外审 catch)**: **forcing 半边真落地, projection 半边仍是未接线契约** —— 见各 Design 的诚实边界段, 别 over-read 成"全部数字都被守住"。

## Design A — 数字单一来源 (doc-currency 治本)
- **核心节点 (主体)**: `docs/research/p1_2_spike_sizing_gate_20260601/authoritative_numbers.json` (cuts 计数 / sizing 6 / F3 / remap, 带 provenance)。
- **生成器**: `scripts/gen_authoritative_numbers.py` (`--check` mode + `current_claims()` build 注入出口)。`sizing_gate.compute_sizing_numbers()` 是 sizing 的出口。
- **强制函数**: `src/tests/test_authoritative_numbers_currency.py` —— 断言核心节点 == 实时计算 (cuts 从 `pytest --collect-only src/tests/cuts` 现数; 实测生效: 加 12 meta-test 后 425→437 立刻报 stale)。
- **关键设计教训 (踩过)**:
  1. **不扫散文找旧数字** —— 文档 meta-讨论数字 (changelog 引旧值当历史 `413→414→416→418`; build 注 "别把 36/50 读成 72%"), 裸扫到处误报。robust 强制函数 = "核心节点 == 实时计算" (零误报); 包 README 拟用 build 期注入 (但**未接线**, 见 #4)。
  2. **数据位置约束**: sizing fixture 在 `data/cuts/spike/` (build 时从 spike 分支 overlay, master working tree 无) → master 侧不现算 sizing, 是冻结 spike 值; 仅 cuts 计数 master 可现算。
  3. **build 脚本的 changelog/历史字面量冻结** (满是合法历史 `413 v17→...`), 不回头改 (同 spike v20 telemetry provenance)。包 README 的**当前 claim** 数字**应**由 `current_claims()` 注入 (历史不动) —— 但**当前未接线** (见 #4)。
  4. **诚实边界 (Design A, 对称于 Design B)**: master 上强制函数**只焊 cuts_tests_total**; sizing/F3/remap 在 master 不被守 (冻结值, 仅 spike/包上下文可验)。**projection 完全未接线**: current_claims() 出口建了但**零消费者**, build_v28 仍硬编码 418 vs 核心节点 441, 强制函数**不扫 projection_targets** → 这类 README 漂移**不自动报红**。--check 也没接 CI/pre-commit 硬 gate (本机 pre-commit 仅 warn)。

## Design B — 共享 SoT 校验 (cut-family)
- **核心节点**: `src/cuts/helpers/canonical_sot.py` (`lookup_canonical_pole_radius` + `lookup_canonical_template_dims` + `validate_template_dims_sot`, 全 fail-closed)。v28 修复时 F7/F8 各被我复制了一份 lookup → 抽成单一实现, F7/F8 委托。
- **强制函数 (meta-test)**: `src/tests/cuts/test_canonical_sot_coverage.py` —— 登记契约 (哪个 family 守哪个 canonical 标量 + 对应 behavioral red-test) + 断言 family 用共享 helper + 私有 lookup (`get("power_coverage_radius")`) 不复活。
- **诚实边界**: meta-test 抓**回归** (refactor 删 guard / 私有 radius lookup 复活 / behavioral test 被删——后两条 v28 外审后补的断言); **发现"全新未守标量"仍靠人/审查** (像 v28 这轮)。私有-lookup 扫描只 scope `power_coverage_radius` (变量间接访问仍漏); **dimensions 私有副本不自动覆盖** —— F6 (shape_packing_hall) 就有一份 sound-but-未走 helper 的 canonical-dims SoT 核对 (fail-closed, 非洞, 但未 consolidate)。不吹成能自动发现新洞。

## 通用原则 (这套架构的灵魂, 同 [[memory-currency-protocol]])
**"强制函数才是解, 规则只是 fallback"** —— 别靠"记得手动同步所有镜像"。核心节点持唯一真值, **被强制函数守的那部分** drift → 响亮红 (本架构里 = master 的 cuts_tests_total)。但**没接强制函数 / 未接线的投影那部分仍会静默漂** (诚实: 本架构目前 force 半边真、project 半边未接 —— 别把灵魂口号当成"全都守住了")。能指针/注入就别 copy 值。

## 链
- [[memory-currency-protocol]] —— 同架构给 handoff 现状 (核心节点=LATEST_PACKAGE.json, 投影=stamp_living_status)
- [[review-pkg-data-completeness]] —— 包数字完整性
- runbook 入口见 `CLAUDE.md` "数字单一来源 (authoritative_numbers core node)" 段
