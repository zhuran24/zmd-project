---
name: no-rust-rewrite-correctness-not-safety
description: "用户问\"审了快30次还在找问题, 会是 Python 问题吗/换 Rust 更安全?\" → 不换 Rust。Rust 治的是内存安全, 而本项目的瓶颈/审查 finding 全是另一类 (校验逻辑正确性 + 文档纪律 + CP-SAT C++ 核的数学), 换 Rust 求解层零收益且清空已硬化的 soundness 成果。"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ca5783d1-e3be-4591-8cfd-4ede5ed83635
---

2026-06-04 用户问: certified-exact 求解器审了快 30 次还在出 finding, 是不是 Python 的问题、换 Rust 会不会更安全 ("听说 Rust 代码安全性特别强")。**结论: 不换 Rust。** 这是个"工具背锅"的归因, 但 Rust 治的病我们没有。

**Why (劈清两类"安全")**:
- **Rust 的"安全" = 内存安全** (use-after-free / 缓冲区溢出 / 数据竞争 / 空指针), 编译期 borrow checker 强制, 保证运行时不崩、不乱写内存。
- **30 轮审查找到的全是另一类**: (a) **校验逻辑 / 语义漏** (F7 fail-open、F5 slot-collision lift、F9 量词倒置 —— 这些 Rust 照样编译通过, borrow checker 不知道"cut 证书是否 sound"); (b) **doc-currency 文档数字陈旧**; (c) **sizing 数学建模**。没一类是内存崩溃。
- **真热点在 C++ 已经**: 30GB 是 CP-SAT 的 propagation buffer, 卡顿是 latency-bound 指针追逐 (280K pose L3 spill), 全在 OR-Tools 的 **C++ 内核**。Python 只是建模 + Benders 外循环胶水, 占比极小 → 换 Rust 求解层**零收益**; 且 OR-Tools 无成熟 Rust 绑定 (要么 FFI 进同一 C++ 核零收益, 要么换 solver——HiGHS 那条路记忆里 42GB 撑死)。
- **重写会清空 30 轮 soundness 硬化成果**, 重新打开全部 FP 风险, 还得再审 30 轮重建信任。

**真正能减审查轮数的是语言无关的结构性修法**: 数字单一来源 (核心节点 + drift-test) + 共享 SoT helper + meta-test (见 [[authoritative-numbers-single-source]]) —— 把"改一处漏多处"的 doc-currency 长尾 + 私有 SoT 副本发散从根上消掉。

**怎么用**: 再遇"换 X 语言/框架更好吗"类归因, 先分清"那语言治的是哪类病 vs 我们的 finding/瓶颈是哪类"。本项目: 瓶颈 = 数学正确性 + 文档纪律 + CP-SAT C++ 核, **不是内存安全**。区别于 v14-review-findings(已归档) / phase0-b-prep-progress(已归档) 里记的"Rust perf bitset kernel defer Phase 2"(那是性能微优化框架, 跟"换语言治安全"完全两回事, 不能混)。

## 链
- [[paradigm-death-timeline-27-lever]] —— 重写路径全穷尽 (单机准确性必保, 决定性收益物理不可达)
- [[authoritative-numbers-single-source]] —— 真正减审查轮数的语言无关修法
